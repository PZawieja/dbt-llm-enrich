import argparse
import json
import sys

from . import config
from .cache import ClassificationCache, PromptDrift
from .client import BatchClient, SyncClient, has_credentials
from .enrich import execute, load_runs, load_tickets, make_plan
from .evaluate import format_report, load_golden, score
from .gate import evaluate_gate
from .prompts import PromptError, load_prompt


def _context(args):
    prompt = load_prompt(args.prompt)
    cache = ClassificationCache(config.CACHE_PATH)
    tickets = load_tickets(config.DUCKDB_PATH)
    runs = load_runs(config.RUNS_PATH)
    return prompt, cache, tickets, runs


def _print_plan(plan) -> None:
    p = plan.prompt
    print(
        f"prompt {p.version} ({p.prompt_hash}) on {p.model}: "
        f"{plan.tickets_seen} tickets, {plan.distinct_texts} distinct texts, "
        f"{plan.cache_hits} cached, {len(plan.to_send)} to send"
        + (f", estimated ${plan.est_cost_usd:.4f}" if plan.to_send else "")
    )


def cmd_plan(args) -> int:
    prompt, cache, tickets, runs = _context(args)
    _print_plan(make_plan(tickets, cache, prompt, runs, batch=not args.sync))
    return 0


def cmd_run(args) -> int:
    prompt, cache, tickets, runs = _context(args)
    plan = make_plan(tickets, cache, prompt, runs, batch=not args.sync)
    _print_plan(plan)
    if not plan.to_send:
        print("nothing to send: every ticket is answered from the cache")
        return 0
    if not has_credentials():
        print(
            f"ANTHROPIC_API_KEY is not set, so {len(plan.to_send)} texts stay "
            "unclassified (they show up as 'missing' in int_ticket_classifications)"
        )
        return 1 if args.require_complete else 0
    if plan.est_cost_usd > args.max_cost:
        print(f"estimated cost is above --max-cost ${args.max_cost:.2f}; not sending")
        return 2
    import anthropic

    client = SyncClient() if args.sync else BatchClient()
    try:
        record = execute(plan, client, cache, config.RUNS_PATH)
    except anthropic.AuthenticationError as exc:
        print(f"the API rejected the key ({exc.status_code}); nothing was sent")
        return 3
    print(
        f"run {record.run_id}: {record.succeeded} classified, {record.errored} failed, "
        f"{record.input_tokens:,} in / {record.output_tokens:,} out tokens, "
        f"${record.cost_usd:.4f}"
    )
    return 1 if args.require_complete and record.errored else 0


def cmd_eval(args) -> int:
    golden = load_golden(config.GOLDEN_PATH)
    cache = ClassificationCache(config.CACHE_PATH)
    tickets = load_tickets(config.DUCKDB_PATH)
    runs = load_runs(config.RUNS_PATH)
    versions = args.prompt or [None]
    reports = [score(load_prompt(v), golden, tickets, cache, runs) for v in versions]
    for report in reports:
        print(format_report(report))
    current = reports[-1]
    if args.save_baseline:
        baseline = {
            "prompt_version": current["prompt_version"],
            "category_accuracy_pct": current["accuracy_pct"]["category"],
            "cost_per_1k_usd": current["cost_per_1k_usd"],
        }
        config.BASELINE_PATH.parent.mkdir(parents=True, exist_ok=True)
        config.BASELINE_PATH.write_text(json.dumps(baseline, indent=2) + "\n")
        print(f"baseline saved to {config.BASELINE_PATH.name}")
        return 0
    if args.gate:
        baseline = json.loads(config.BASELINE_PATH.read_text())
        result = evaluate_gate(current, baseline)
        if result["passed"]:
            print(f"gate passed against baseline ({baseline['prompt_version']})")
            return 0
        print("gate FAILED:\n  " + "\n  ".join(result["reasons"]))
        return 1
    return 0


def cmd_report(args) -> int:
    runs = load_runs(config.RUNS_PATH)
    if not runs:
        print("no runs yet")
        return 0
    print(
        f"{'run':<26}{'mode':<7}{'sent':>6}{'ok':>6}{'hits':>6}"
        f"{'tokens in/out':>18}{'cost':>10}"
    )
    for r in runs:
        tokens = f"{r['input_tokens']:,}/{r['output_tokens']:,}"
        print(
            f"{r['run_id']:<26}{r['mode']:<7}{r['sent']:>6}{r['succeeded']:>6}"
            f"{r['cache_hits']:>6}{tokens:>18}{r['cost_usd']:>10.4f}"
        )
    print(f"total ${sum(r['cost_usd'] for r in runs):.4f}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="enrich", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("plan", help="show what a run would send and what it would cost")
    p.add_argument("--prompt", help="prompt version (default: current)")
    p.add_argument("--sync", action="store_true")
    p.set_defaults(func=cmd_plan)

    p = sub.add_parser("run", help="classify every ticket the cache doesn't cover")
    p.add_argument("--prompt", help="prompt version (default: current)")
    p.add_argument(
        "--sync", action="store_true", help="Messages API instead of a batch"
    )
    p.add_argument(
        "--require-complete",
        action="store_true",
        help="exit 1 if any ticket is left without a classification",
    )
    p.add_argument("--max-cost", type=float, default=config.DEFAULT_MAX_COST_USD)
    p.set_defaults(func=cmd_run)

    p = sub.add_parser(
        "eval", help="score cached classifications against golden labels"
    )
    p.add_argument("--prompt", action="append", help="version(s) to score, in order")
    p.add_argument("--gate", action="store_true", help="fail on regression vs baseline")
    p.add_argument("--save-baseline", action="store_true")
    p.set_defaults(func=cmd_eval)

    p = sub.add_parser("report", help="list enrichment runs and their cost")
    p.set_defaults(func=cmd_report)

    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (PromptError, PromptDrift) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
