import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DBT_DIR = ROOT / "warehouse" / "dbt"
DUCKDB_PATH = Path(os.environ.get("ENRICH_DUCKDB_PATH", DBT_DIR / "ledgerkite.duckdb"))
PROMPTS_PATH = ROOT / "prompts" / "classify_ticket.yml"
CACHE_PATH = ROOT / "enrichment" / "classifications.jsonl"
RUNS_PATH = ROOT / "enrichment" / "runs.jsonl"
GOLDEN_PATH = DBT_DIR / "seeds" / "golden_ticket_labels.csv"
BASELINE_PATH = ROOT / "eval" / "baseline.json"

MAX_TOKENS = 400
POLL_SECONDS = 15
DEFAULT_MAX_COST_USD = 1.00
