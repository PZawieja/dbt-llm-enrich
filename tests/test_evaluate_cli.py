import json

from dbt_llm_enrich import cli, config
from dbt_llm_enrich.cache import ClassificationCache
from dbt_llm_enrich.client import FakeClient
from dbt_llm_enrich.enrich import execute, make_plan
from dbt_llm_enrich.evaluate import score
from dbt_llm_enrich.gate import evaluate_gate
from dbt_llm_enrich.prompts import load_prompt

GOLDEN = [
    {
        "ticket_id": "T-1",
        "category": "cancellation",
        "urgency": "normal",
        "sentiment": "neutral",
        "churn_signal": True,
        "language": "en",
        "trap": "",
    },
    {
        "ticket_id": "T-2",
        "category": "access",
        "urgency": "high",
        "sentiment": "negative",
        "churn_signal": False,
        "language": "en",
        "trap": "injection",
    },
    {
        "ticket_id": "T-4",
        "category": "how_to",
        "urgency": "low",
        "sentiment": "neutral",
        "churn_signal": False,
        "language": "en",
        "trap": "",
    },
]


def test_score_counts_missing_as_wrong(tickets, cache, tmp_path):
    prompt = load_prompt("v1")
    empty = score(prompt, GOLDEN, tickets, cache, [])
    assert empty["missing"] == 3 and empty["accuracy_pct"]["category"] == 0

    execute(
        make_plan(tickets, cache, prompt, []),
        FakeClient(),
        cache,
        tmp_path / "r",
        log=lambda _: None,
    )
    report = score(prompt, GOLDEN, tickets, cache, [])
    assert report["missing"] == 0
    assert report["accuracy_pct"]["category"] == 100.0
    assert report["per_class"]["access"]["recall"] == 1.0
    assert report["injection"] == {"tickets": 1, "category_and_urgency_ok": 0}


def test_gate():
    report = {"accuracy_pct": {"category": 90.0}, "missing": 0, "cost_per_1k_usd": 0.05}
    assert evaluate_gate(
        report, {"category_accuracy_pct": 91.0, "cost_per_1k_usd": 0.05}
    )["passed"]
    worse = evaluate_gate(
        report, {"category_accuracy_pct": 93.0, "cost_per_1k_usd": 0.03}
    )
    assert not worse["passed"] and len(worse["reasons"]) == 2


def test_run_without_key(paths, monkeypatch, capsys):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    assert cli.main(["run"]) == 0
    assert cli.main(["run", "--require-complete"]) == 1
    assert "3 texts stay unclassified" in capsys.readouterr().out
    assert not config.RUNS_PATH.exists()


def test_replay_from_a_complete_cache_needs_no_key(paths, monkeypatch, tickets):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cache = ClassificationCache(config.CACHE_PATH)
    plan = make_plan(tickets, cache, load_prompt(), [])
    execute(plan, FakeClient(), cache, config.RUNS_PATH, log=lambda _: None)
    assert cli.main(["run", "--require-complete"]) == 0
    assert len(config.RUNS_PATH.read_text().splitlines()) == 1


def test_max_cost_guard(paths, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
    assert cli.main(["run", "--max-cost", "0"]) == 2
    assert not config.CACHE_PATH.exists()


def test_baseline_round_trip(paths, monkeypatch, tickets):
    golden = paths / "golden.csv"
    golden.write_text(
        "ticket_id,category,urgency,sentiment,churn_signal,language,trap\n"
        "T-1,cancellation,normal,neutral,true,en,\n"
    )
    monkeypatch.setattr(config, "GOLDEN_PATH", golden)
    cache = ClassificationCache(config.CACHE_PATH)
    execute(
        make_plan(tickets, cache, load_prompt(), []),
        FakeClient(),
        cache,
        config.RUNS_PATH,
        log=lambda _: None,
    )
    assert cli.main(["eval", "--save-baseline"]) == 0
    assert (
        json.loads(config.BASELINE_PATH.read_text())["category_accuracy_pct"] == 100.0
    )
    assert cli.main(["eval", "--gate"]) == 0
