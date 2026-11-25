CATEGORIES = [
    "billing",
    "bug",
    "access",
    "feature_request",
    "how_to",
    "cancellation",
    "data_export",
    "other",
]
URGENCIES = ["low", "normal", "high"]
SENTIMENTS = ["negative", "neutral", "positive"]
LANGUAGES = ["en", "de", "fr", "es", "pl", "other"]
LABELS = ["category", "urgency", "sentiment", "churn_signal", "language"]

OUTPUT_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "urgency": {"type": "string", "enum": URGENCIES},
        "sentiment": {"type": "string", "enum": SENTIMENTS},
        "churn_signal": {"type": "boolean"},
        "language": {"type": "string", "enum": LANGUAGES},
    },
    "required": LABELS,
    "additionalProperties": False,
}

_ENUMS = {
    "category": CATEGORIES,
    "urgency": URGENCIES,
    "sentiment": SENTIMENTS,
    "language": LANGUAGES,
}


class InvalidOutput(ValueError):
    pass


def validate(result: dict) -> dict:
    if set(result) != set(LABELS):
        raise InvalidOutput(f"expected keys {LABELS}, got {sorted(result)}")
    for key, allowed in _ENUMS.items():
        if result[key] not in allowed:
            raise InvalidOutput(f"{key}={result[key]!r} is not one of {allowed}")
    if not isinstance(result["churn_signal"], bool):
        raise InvalidOutput("churn_signal must be a boolean")
    return result
