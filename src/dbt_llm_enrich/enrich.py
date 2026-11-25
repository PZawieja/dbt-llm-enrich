import json
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path

import duckdb

from .cache import Classification, ClassificationCache, cache_key
from .client import build_params
from .cost import cost_usd
from .prompts import Prompt

FALLBACK_OUTPUT_TOKENS = 60


@dataclass(frozen=True)
class Ticket:
    ticket_id: str
    content_hash: str
    ticket_text: str


@dataclass
class Plan:
    prompt: Prompt
    tickets_seen: int
    distinct_texts: int
    cache_hits: int
    to_send: dict[str, str]
    est_cost_usd: float


@dataclass
class RunRecord:
    run_id: str
    started_at: str
    finished_at: str
    mode: str
    prompt_version: str
    prompt_hash: str
    model: str
    tickets_seen: int
    distinct_texts: int
    cache_hits: int
    sent: int
    succeeded: int
    errored: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    batch_id: str | None


def load_tickets(db_path: Path) -> list[Ticket]:
    with duckdb.connect(str(db_path), read_only=True) as con:
        rows = con.sql(
            "SELECT ticket_id, content_hash, ticket_text "
            "FROM staging.stg_tickets ORDER BY ticket_id"
        ).fetchall()
    return [Ticket(*r) for r in rows]


def load_runs(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def estimate_cost(
    texts: dict[str, str], prompt: Prompt, runs: list[dict], batch: bool = True
) -> float:
    if not texts:
        return 0.0
    past = [r for r in runs if r["model"] == prompt.model and r["succeeded"]]
    if past:
        done = sum(r["succeeded"] for r in past)
        per_in = sum(r["input_tokens"] for r in past) / done
        per_out = sum(r["output_tokens"] for r in past) / done
    else:
        # Rough first-run guess: about 3 characters per token on the newer tokenizer.
        chars = sum(len(t) for t in texts.values()) / len(texts)
        per_in = (len(prompt.system) + chars) / 3
        per_out = FALLBACK_OUTPUT_TOKENS
    n = len(texts)
    return cost_usd(prompt.model, round(per_in * n), round(per_out * n), batch)


def make_plan(
    tickets: list[Ticket],
    cache: ClassificationCache,
    prompt: Prompt,
    runs: list[dict],
    batch: bool = True,
) -> Plan:
    cache.check_drift(prompt.version, prompt.prompt_hash, prompt.model)
    distinct = {t.content_hash: t.ticket_text for t in tickets}
    to_send = {
        h: text
        for h, text in distinct.items()
        if cache_key(h, prompt.prompt_hash, prompt.model) not in cache
    }
    return Plan(
        prompt=prompt,
        tickets_seen=len(tickets),
        distinct_texts=len(distinct),
        cache_hits=len(distinct) - len(to_send),
        to_send=to_send,
        est_cost_usd=estimate_cost(to_send, prompt, runs, batch),
    )


def _now() -> datetime:
    return datetime.now(UTC).replace(microsecond=0)


def execute(
    plan: Plan,
    client,
    cache: ClassificationCache,
    runs_path: Path,
    log: Callable[[str], None] = print,
) -> RunRecord:
    prompt = plan.prompt
    started = _now()
    run_id = f"{started:%Y%m%dT%H%M%SZ}-{prompt.version}"
    requests = {h: build_params(prompt, text) for h, text in plan.to_send.items()}
    batch_id, results = client.run(requests, log)

    rows, errored = [], 0
    for r in results:
        if r.status != "succeeded":
            errored += 1
            log(f"  {r.custom_id[:12]}… {r.status} {r.error or ''}".rstrip())
            continue
        rows.append(
            Classification(
                cache_key=cache_key(r.custom_id, prompt.prompt_hash, prompt.model),
                content_hash=r.custom_id,
                prompt_version=prompt.version,
                prompt_hash=prompt.prompt_hash,
                model=prompt.model,
                run_id=run_id,
                classified_at=_now().isoformat(),
                input_tokens=r.input_tokens,
                output_tokens=r.output_tokens,
                **r.output,
            )
        )
    cache.append(rows)

    input_tokens = sum(r.input_tokens for r in results)
    output_tokens = sum(r.output_tokens for r in results)
    record = RunRecord(
        run_id=run_id,
        started_at=started.isoformat(),
        finished_at=_now().isoformat(),
        mode=client.mode,
        prompt_version=prompt.version,
        prompt_hash=prompt.prompt_hash,
        model=prompt.model,
        tickets_seen=plan.tickets_seen,
        distinct_texts=plan.distinct_texts,
        cache_hits=plan.cache_hits,
        sent=len(requests),
        succeeded=len(rows),
        errored=errored,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost_usd(
            prompt.model, input_tokens, output_tokens, batch=client.mode == "batch"
        ),
        batch_id=batch_id,
    )
    runs_path.parent.mkdir(parents=True, exist_ok=True)
    with runs_path.open("a") as f:
        f.write(json.dumps(asdict(record)) + "\n")
    return record
