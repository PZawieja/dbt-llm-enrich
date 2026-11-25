import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path


def cache_key(content_hash: str, prompt_hash: str, model: str) -> str:
    return hashlib.sha256(f"{content_hash}|{prompt_hash}|{model}".encode()).hexdigest()


@dataclass(frozen=True)
class Classification:
    cache_key: str
    content_hash: str
    prompt_version: str
    prompt_hash: str
    model: str
    category: str
    urgency: str
    sentiment: str
    churn_signal: bool
    language: str
    run_id: str
    classified_at: str
    input_tokens: int
    output_tokens: int


class PromptDrift(RuntimeError):
    pass


class ClassificationCache:
    def __init__(self, path: Path):
        self.path = path
        self._rows: dict[str, Classification] = {}
        if path.exists():
            for line in path.read_text().splitlines():
                if line.strip():
                    row = Classification(**json.loads(line))
                    self._rows[row.cache_key] = row

    def __contains__(self, key: str) -> bool:
        return key in self._rows

    def __len__(self) -> int:
        return len(self._rows)

    def get(self, key: str) -> Classification | None:
        return self._rows.get(key)

    def rows(self) -> list[Classification]:
        return list(self._rows.values())

    def check_drift(self, version: str, prompt_hash: str, model: str) -> None:
        stale = {
            r.prompt_hash
            for r in self._rows.values()
            if r.prompt_version == version and r.model == model
        } - {prompt_hash}
        if stale:
            raise PromptDrift(
                f"prompt {version} changed since it was cached (hash {prompt_hash}, "
                f"cache has {sorted(stale)}). Give the edited prompt a new version "
                "label so old and new results stay comparable."
            )

    def append(self, rows: list[Classification]) -> None:
        new = {r.cache_key: r for r in rows if r.cache_key not in self._rows}
        if not new:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as f:
            for row in new.values():
                f.write(json.dumps(asdict(row), sort_keys=True) + "\n")
        self._rows.update(new)
