import json
import os
import time
from collections.abc import Callable
from dataclasses import dataclass

from . import config
from .prompts import Prompt
from .schema import OUTPUT_SCHEMA, InvalidOutput, validate


@dataclass(frozen=True)
class Result:
    custom_id: str
    status: str
    output: dict | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    error: str | None = None


def has_credentials() -> bool:
    return bool(
        os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")
    )


def build_params(prompt: Prompt, ticket_text: str) -> dict:
    # Ticket text is customer-written, so it goes in the user turn as tagged data
    # and the schema limits the answer to the enums whatever the ticket says.
    return {
        "model": prompt.model,
        "max_tokens": config.MAX_TOKENS,
        "system": prompt.system,
        "thinking": {"type": "disabled"},
        "output_config": {
            "effort": "low",
            "format": {"type": "json_schema", "schema": OUTPUT_SCHEMA},
        },
        "messages": [
            {"role": "user", "content": f"<ticket>\n{ticket_text}\n</ticket>"}
        ],
    }


def parse_message(custom_id: str, message) -> Result:
    usage = message.usage
    tokens = {
        "input_tokens": usage.input_tokens,
        "output_tokens": usage.output_tokens,
    }
    if message.stop_reason != "end_turn":
        return Result(custom_id, "errored", error=message.stop_reason, **tokens)
    text = next((b.text for b in message.content if b.type == "text"), "")
    try:
        output = validate(json.loads(text))
    except (json.JSONDecodeError, InvalidOutput) as exc:
        return Result(custom_id, "errored", error=f"invalid output: {exc}", **tokens)
    return Result(custom_id, "succeeded", output=output, **tokens)


class BatchClient:
    mode = "batch"

    def __init__(self, client=None, poll_seconds: int = config.POLL_SECONDS):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self.poll_seconds = poll_seconds

    def run(
        self, requests: dict[str, dict], log: Callable[[str], None] = print
    ) -> tuple[str, list[Result]]:
        batch = self.client.messages.batches.create(
            requests=[{"custom_id": cid, "params": p} for cid, p in requests.items()]
        )
        log(f"batch {batch.id} submitted with {len(requests)} requests")
        while batch.processing_status != "ended":
            time.sleep(self.poll_seconds)
            batch = self.client.messages.batches.retrieve(batch.id)
            c = batch.request_counts
            log(
                f"  {batch.processing_status}: {c.processing} processing, "
                f"{c.succeeded} succeeded, {c.errored} errored"
            )
        results = []
        for item in self.client.messages.batches.results(batch.id):
            if item.result.type == "succeeded":
                results.append(parse_message(item.custom_id, item.result.message))
            else:
                error = getattr(item.result, "error", None)
                results.append(
                    Result(item.custom_id, item.result.type, error=str(error or ""))
                )
        return batch.id, results


class SyncClient:
    mode = "sync"

    def __init__(self, client=None):
        import anthropic

        self.client = client or anthropic.Anthropic()
        self._api_error = anthropic.APIError

    def run(
        self, requests: dict[str, dict], log: Callable[[str], None] = print
    ) -> tuple[None, list[Result]]:
        results = []
        for i, (cid, params) in enumerate(requests.items(), 1):
            try:
                message = self.client.messages.create(**params)
                results.append(parse_message(cid, message))
            except self._api_error as exc:
                results.append(Result(cid, "errored", error=str(exc)))
            if i % 25 == 0:
                log(f"  {i}/{len(requests)} done")
        return None, results


KEYWORDS = [
    ("cancellation", ("cancel", "renew", "close our account", "kündig", "résili")),
    ("access", ("log in", "2fa", "invite", "admin rights", "sso", "former employee")),
    (
        "data_export",
        ("export of all", "gdpr", "api endpoint", "migrating", "client list"),
    ),
    (
        "bug",
        ("blank", "twice to", "went out twice", "crash", "stuck", "wrong", "fails"),
    ),
    (
        "feature_request",
        ("would really help", "could you add", "any plans", "we'd like"),
    ),
    ("billing", ("charged", "invoice from ledgerkite", "seats", "price", "receipts")),
    ("how_to", ("how do i", "how can i", "where do i", "is it possible")),
]


class FakeClient:
    """Deterministic keyword classifier for tests; never calls the API."""

    def __init__(self, mode: str = "batch", fail: set[str] | None = None):
        self.mode = mode
        self.fail = fail or set()
        self.sent: list[str] = []

    def run(self, requests: dict[str, dict], log: Callable[[str], None] = print):
        results = []
        for cid, params in requests.items():
            self.sent.append(cid)
            if cid in self.fail:
                results.append(Result(cid, "expired"))
                continue
            text = params["messages"][0]["content"].lower()
            category = next(
                (c for c, words in KEYWORDS if any(w in text for w in words)), "other"
            )
            output = {
                "category": category,
                "urgency": "high" if "urgent" in text else "normal",
                "sentiment": "neutral",
                "churn_signal": category == "cancellation",
                "language": "en",
            }
            results.append(Result(cid, "succeeded", output, len(text) // 3, 30))
        return ("fake-batch" if self.mode == "batch" else None), results
