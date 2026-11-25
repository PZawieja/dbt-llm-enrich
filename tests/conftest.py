import hashlib

import duckdb
import pytest

from dbt_llm_enrich import config
from dbt_llm_enrich.cache import ClassificationCache
from dbt_llm_enrich.enrich import Ticket

TEXTS = {
    "T-1": "Subject: Cancel\n\nPlease cancel our subscription.",
    "T-2": "Subject: Login\n\nI can't log in after a password reset.",
    "T-3": "Subject: Cancel\n\nPlease cancel our subscription.",
    "T-4": "Subject: How\n\nHow do I add our logo?",
}


def make_ticket(ticket_id: str, text: str) -> Ticket:
    return Ticket(ticket_id, hashlib.sha256(text.encode()).hexdigest(), text)


@pytest.fixture
def tickets() -> list[Ticket]:
    return [make_ticket(i, t) for i, t in TEXTS.items()]


@pytest.fixture
def paths(tmp_path, monkeypatch, tickets):
    db = tmp_path / "w.duckdb"
    with duckdb.connect(str(db)) as con:
        con.execute("CREATE SCHEMA staging")
        con.execute(
            "CREATE TABLE staging.stg_tickets "
            "(ticket_id VARCHAR, content_hash VARCHAR, ticket_text VARCHAR)"
        )
        con.executemany(
            "INSERT INTO staging.stg_tickets VALUES (?, ?, ?)",
            [(t.ticket_id, t.content_hash, t.ticket_text) for t in tickets],
        )
    monkeypatch.setattr(config, "DUCKDB_PATH", db)
    monkeypatch.setattr(config, "CACHE_PATH", tmp_path / "cache.jsonl")
    monkeypatch.setattr(config, "RUNS_PATH", tmp_path / "runs.jsonl")
    monkeypatch.setattr(config, "BASELINE_PATH", tmp_path / "baseline.json")
    return tmp_path


@pytest.fixture
def cache(tmp_path) -> ClassificationCache:
    return ClassificationCache(tmp_path / "cache.jsonl")
