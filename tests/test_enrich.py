import json

from conftest import make_ticket

from dbt_llm_enrich.cache import ClassificationCache
from dbt_llm_enrich.client import FakeClient
from dbt_llm_enrich.enrich import estimate_cost, execute, load_runs, make_plan
from dbt_llm_enrich.prompts import load_prompt

QUIET = {"log": lambda _: None}


def test_duplicates_collapse_to_one_request(tickets, cache):
    plan = make_plan(tickets, cache, load_prompt("v1"), [])
    assert (plan.tickets_seen, plan.distinct_texts, len(plan.to_send)) == (4, 3, 3)


def test_run_caches_results_and_the_next_run_sends_nothing(tickets, cache, tmp_path):
    runs = tmp_path / "runs.jsonl"
    prompt = load_prompt("v1")
    record = execute(
        make_plan(tickets, cache, prompt, []), FakeClient(), cache, runs, **QUIET
    )
    assert (record.sent, record.succeeded, record.errored) == (3, 3, 0)
    assert record.mode == "batch" and record.batch_id == "fake-batch"
    assert record.cost_usd > 0

    reloaded = ClassificationCache(cache.path)
    again = make_plan(tickets, reloaded, prompt, load_runs(runs))
    assert again.to_send == {} and again.cache_hits == 3
    assert json.loads(runs.read_text())["run_id"] == record.run_id


def test_failed_requests_are_not_cached_and_retry_next_time(tickets, cache, tmp_path):
    prompt = load_prompt("v1")
    plan = make_plan(tickets, cache, prompt, [])
    failing = tickets[1].content_hash
    record = execute(plan, FakeClient(fail={failing}), cache, tmp_path / "r", **QUIET)
    assert (record.succeeded, record.errored) == (2, 1)
    assert list(make_plan(tickets, cache, prompt, []).to_send) == [failing]


def test_edited_ticket_is_the_only_one_resent(tickets, cache, tmp_path):
    prompt = load_prompt("v1")
    execute(
        make_plan(tickets, cache, prompt, []),
        FakeClient(),
        cache,
        tmp_path / "r",
        **QUIET,
    )
    edited = [
        *tickets[:3],
        make_ticket("T-4", tickets[3].ticket_text + "\n\nUpdate: urgent"),
    ]
    plan = make_plan(edited, cache, prompt, [])
    assert list(plan.to_send) == [edited[3].content_hash]


def test_new_prompt_version_resends_everything(tickets, cache, tmp_path):
    execute(
        make_plan(tickets, cache, load_prompt("v1"), []),
        FakeClient(),
        cache,
        tmp_path / "r",
        **QUIET,
    )
    assert len(make_plan(tickets, cache, load_prompt("v2"), []).to_send) == 3


def test_estimate_uses_past_runs_when_available(tickets):
    prompt = load_prompt("v1")
    texts = {t.content_hash: t.ticket_text for t in tickets}
    past = [
        {
            "model": prompt.model,
            "prompt_version": "v1",
            "succeeded": 10,
            "input_tokens": 10_000,
            "output_tokens": 500,
        }
    ]
    # 3 texts x 1,000 in + 50 out at batch prices.
    assert estimate_cost(texts, prompt, past) == round(
        (3000 * 0.10 + 150 * 0.50) / 1e6 / 2, 6
    )


def test_estimate_for_a_new_prompt_adds_the_longer_system_prompt(tickets):
    v1, v2 = load_prompt("v1"), load_prompt("v2")
    texts = {t.content_hash: t.ticket_text for t in tickets}
    past = [
        {
            "model": v1.model,
            "prompt_version": "v1",
            "succeeded": 10,
            "input_tokens": 10_000,
            "output_tokens": 500,
        }
    ]
    assert estimate_cost(texts, v2, past) > estimate_cost(texts, v1, past)
