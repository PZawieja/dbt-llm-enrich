import csv
from collections import Counter
from pathlib import Path

from .cache import ClassificationCache, cache_key
from .enrich import Ticket
from .prompts import Prompt
from .schema import CATEGORIES, LABELS


def load_golden(path: Path) -> list[dict]:
    with path.open() as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["churn_signal"] = r["churn_signal"] == "true"
    return rows


def score(
    prompt: Prompt,
    golden: list[dict],
    tickets: list[Ticket],
    cache: ClassificationCache,
    runs: list[dict],
) -> dict:
    hashes = {t.ticket_id: t.content_hash for t in tickets}
    correct = Counter()
    confusion: Counter = Counter()
    missing = 0
    injection_total = injection_ok = 0
    for g in golden:
        pred = cache.get(
            cache_key(hashes[g["ticket_id"]], prompt.prompt_hash, prompt.model)
        )
        if pred is None:
            missing += 1
            confusion[(g["category"], "missing")] += 1
        else:
            for label in LABELS:
                correct[label] += getattr(pred, label) == g[label]
            confusion[(g["category"], pred.category)] += 1
        if g["trap"] == "injection":
            injection_total += 1
            injection_ok += bool(
                pred and pred.category == g["category"] and pred.urgency == g["urgency"]
            )

    n = len(golden)
    per_class = {}
    for cat in CATEGORIES:
        tp = confusion[(cat, cat)]
        predicted = sum(v for (_, p), v in confusion.items() if p == cat)
        actual = sum(v for (a, _), v in confusion.items() if a == cat)
        per_class[cat] = {
            "precision": round(tp / predicted, 3) if predicted else None,
            "recall": round(tp / actual, 3) if actual else None,
            "support": actual,
        }

    version_runs = [
        r
        for r in runs
        if r["prompt_version"] == prompt.version and r["model"] == prompt.model
    ]
    run_cost = sum(r["cost_usd"] for r in version_runs)
    run_done = sum(r["succeeded"] for r in version_runs)
    return {
        "prompt_version": prompt.version,
        "prompt_hash": prompt.prompt_hash,
        "model": prompt.model,
        "golden_tickets": n,
        "missing": missing,
        "accuracy_pct": {k: round(100 * correct[k] / n, 1) for k in LABELS},
        "per_class": per_class,
        "confusion": {f"{a}->{p}": v for (a, p), v in sorted(confusion.items())},
        "injection": {
            "tickets": injection_total,
            "category_and_urgency_ok": injection_ok,
        },
        "cost_usd": round(run_cost, 6),
        "cost_per_1k_usd": round(1000 * run_cost / run_done, 4) if run_done else None,
    }


def format_report(report: dict) -> str:
    acc = report["accuracy_pct"]
    lines = [
        f"prompt {report['prompt_version']} ({report['prompt_hash']}) on "
        f"{report['model']}: {report['golden_tickets']} golden tickets, "
        f"{report['missing']} missing",
        "  accuracy: " + ", ".join(f"{k} {v}%" for k, v in acc.items()),
        f"  prompt-injection tickets: {report['injection']['category_and_urgency_ok']}"
        f"/{report['injection']['tickets']} with category and urgency right",
    ]
    if report["cost_per_1k_usd"] is not None:
        lines.append(
            f"  cost: ${report['cost_usd']:.4f} in runs, "
            f"${report['cost_per_1k_usd']:.4f} per 1,000 tickets classified"
        )
    lines.append("  per category (precision / recall / support):")
    for cat, m in report["per_class"].items():
        p = "-" if m["precision"] is None else f"{m['precision']:.2f}"
        r = "-" if m["recall"] is None else f"{m['recall']:.2f}"
        lines.append(f"    {cat:<16} {p:>5} / {r:>5} / {m['support']}")
    misses = {
        k: v
        for k, v in report["confusion"].items()
        if k.split("->")[0] != k.split("->")[1]
    }
    if misses:
        lines.append(
            "  confusions: " + ", ".join(f"{k} x{v}" for k, v in misses.items())
        )
    return "\n".join(lines)
