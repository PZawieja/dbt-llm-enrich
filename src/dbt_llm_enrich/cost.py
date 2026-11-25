# USD per million tokens, standard tier, prompts up to 100K tokens. Checked
# against the Claude pricing page on 2026-11-25. The Batch API bills half.
PRICES = {"claude-haiku-5-5": {"input": 0.10, "output": 0.50}}
BATCH_DISCOUNT = 0.5


def cost_usd(model: str, input_tokens: int, output_tokens: int, batch: bool) -> float:
    price = PRICES[model]
    usd = (input_tokens * price["input"] + output_tokens * price["output"]) / 1e6
    return round(usd * (BATCH_DISCOUNT if batch else 1.0), 6)
