import pytest

from dbt_llm_enrich.cache import (
    Classification,
    ClassificationCache,
    PromptDrift,
    cache_key,
)
from dbt_llm_enrich.prompts import Prompt, PromptError, load_prompt


def row(content_hash="h1", version="v1", prompt_hash="p1", model="m") -> Classification:
    return Classification(
        cache_key=cache_key(content_hash, prompt_hash, model),
        content_hash=content_hash,
        prompt_version=version,
        prompt_hash=prompt_hash,
        model=model,
        category="bug",
        urgency="high",
        sentiment="negative",
        churn_signal=False,
        language="en",
        run_id="r1",
        classified_at="2026-11-25T10:00:00+00:00",
        input_tokens=100,
        output_tokens=20,
    )


def test_prompt_versions_hash_differently_and_stably():
    v1, v2 = load_prompt("v1"), load_prompt("v2")
    assert v1.prompt_hash != v2.prompt_hash
    assert load_prompt("v2").prompt_hash == v2.prompt_hash
    assert load_prompt().version == "v2"


def test_editing_prompt_text_changes_the_hash():
    a = Prompt("v1", "Classify tickets.", "m")
    b = Prompt("v1", "Classify tickets!", "m")
    assert a.prompt_hash != b.prompt_hash


def test_unknown_version():
    with pytest.raises(PromptError):
        load_prompt("v9")


def test_cache_key_covers_text_prompt_and_model():
    base = cache_key("h", "p", "m")
    assert (
        len(
            {
                base,
                cache_key("h2", "p", "m"),
                cache_key("h", "p2", "m"),
                cache_key("h", "p", "m2"),
            }
        )
        == 4
    )


def test_append_is_idempotent_and_persists(cache):
    cache.append([row(), row()])
    cache.append([row()])
    assert len(cache) == 1
    assert len(cache.path.read_text().splitlines()) == 1
    assert ClassificationCache(cache.path).get(row().cache_key) == row()


def test_drift_guard_rejects_edited_prompt_with_same_label(cache):
    cache.append([row(prompt_hash="old")])
    cache.check_drift("v1", "old", "m")
    cache.check_drift("v2", "new", "m")
    with pytest.raises(PromptDrift, match="new version label"):
        cache.check_drift("v1", "new", "m")
