import csv
import importlib.util
import re

import yaml

from dbt_llm_enrich import config
from dbt_llm_enrich.prompts import current_version
from dbt_llm_enrich.schema import CATEGORIES, LANGUAGES, SENTIMENTS, URGENCIES

spec = importlib.util.spec_from_file_location(
    "generate", config.ROOT / "warehouse" / "generate.py"
)
generate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(generate)


def test_generator_is_deterministic():
    assert generate.build(False) == generate.build(False)


def test_traps_and_language_mix():
    _, tickets = generate.build(False)
    assert len(tickets) == 600
    traps = [t["_trap"] for t in tickets]
    assert traps.count("duplicate") == 30
    assert traps.count("edited") == 20
    assert traps.count("injection") == 12
    non_english = sum(t["_language"] != "en" for t in tickets)
    assert 40 <= non_english <= 90


def test_edits_only_change_edited_tickets():
    _, before = generate.build(True)
    _, after = generate.build(False)
    before = {t["ticket_id"]: t for t in before}
    changed = [t for t in after if t["body"] != before[t["ticket_id"]]["body"]]
    assert len(changed) == 20
    assert all(t["_trap"] == "edited" for t in changed)


def test_committed_seeds_match_the_generator():
    _, tickets = generate.build(False)
    with (config.DBT_DIR / "seeds" / "raw_tickets.csv").open() as f:
        committed = {r["ticket_id"]: r["body"] for r in csv.DictReader(f)}
    assert committed == {t["ticket_id"]: t["body"] for t in tickets}


def test_golden_labels_are_valid_and_cover_every_injection():
    _, tickets = generate.build(False)
    with config.GOLDEN_PATH.open() as f:
        golden = list(csv.DictReader(f))
    assert len(golden) == 150
    assert {r["ticket_id"] for r in golden} >= {
        t["ticket_id"] for t in tickets if t["_trap"] == "injection"
    }
    for r in golden:
        assert r["category"] in CATEGORIES
        assert r["urgency"] in URGENCIES
        assert r["sentiment"] in SENTIMENTS
        assert r["language"] in LANGUAGES
        assert r["churn_signal"] in ("true", "false")


def test_template_labels_use_the_schema_enums():
    t = yaml.safe_load((config.ROOT / "warehouse" / "ticket_templates.yml").read_text())
    groups = [t["en"]] + list(t["native"].values())
    for group in groups:
        for category, templates in group.items():
            assert category in CATEGORIES
            for tpl in templates:
                assert tpl["urgency"] in URGENCIES
                assert tpl["sentiment"] in SENTIMENTS


def test_dbt_prompt_version_matches_prompts_file():
    project = (config.DBT_DIR / "dbt_project.yml").read_text()
    assert re.search(rf"prompt_version: {current_version()}\b", project)
