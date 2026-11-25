# Adapted from harness/gate.py in github.com/PZawieja/llmops-eval-harness:
# compare a run's aggregate with a saved baseline and fail on regressions.
# Latency is dropped because batch latency is queue time, not model speed.
MAX_ACCURACY_DROP_PCT = 2.0
MAX_COST_INCREASE_PCT = 25.0


def evaluate_gate(report: dict, baseline: dict) -> dict:
    reasons = []

    accuracy = report["accuracy_pct"]["category"]
    accuracy_drop = baseline["category_accuracy_pct"] - accuracy
    if accuracy_drop > MAX_ACCURACY_DROP_PCT:
        reasons.append(
            f"category accuracy dropped {accuracy_drop:.1f} points "
            f"({baseline['category_accuracy_pct']:.1f}% -> {accuracy:.1f}%), "
            f"more than the allowed {MAX_ACCURACY_DROP_PCT}"
        )

    if report["missing"]:
        reasons.append(f"{report['missing']} golden tickets have no classification")

    base_cost, cost = baseline.get("cost_per_1k_usd"), report["cost_per_1k_usd"]
    if base_cost and cost is not None:
        increase = (cost - base_cost) / base_cost * 100
        if increase > MAX_COST_INCREASE_PCT:
            reasons.append(
                f"cost per 1,000 tickets rose {increase:.1f}% "
                f"(${base_cost:.4f} -> ${cost:.4f}), "
                f"more than the allowed {MAX_COST_INCREASE_PCT}%"
            )

    return {"passed": not reasons, "reasons": reasons}
