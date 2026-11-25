import hashlib
import json
from dataclasses import dataclass
from pathlib import Path

import yaml

from . import config
from .schema import OUTPUT_SCHEMA


@dataclass(frozen=True)
class Prompt:
    version: str
    system: str
    model: str

    @property
    def prompt_hash(self) -> str:
        payload = json.dumps(
            {"system": self.system, "schema": OUTPUT_SCHEMA}, sort_keys=True
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


class PromptError(ValueError):
    pass


def load_prompt(version: str | None = None, path: Path | None = None) -> Prompt:
    spec = yaml.safe_load((path or config.PROMPTS_PATH).read_text())
    version = version or spec["current"]
    if version not in spec["versions"]:
        raise PromptError(
            f"unknown prompt version {version!r}; have {sorted(spec['versions'])}"
        )
    return Prompt(version, spec["versions"][version]["system"], spec["model"])


def current_version(path: Path | None = None) -> str:
    return yaml.safe_load((path or config.PROMPTS_PATH).read_text())["current"]
