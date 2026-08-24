from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


DEVELOPER_OS_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_ENV_FILE = DEVELOPER_OS_ROOT / ".env"


@dataclass(frozen=True)
class CredentialReadiness:
    orchestration_key_present: bool
    project_id_present: bool
    admin_key_present: bool
    legacy_key_present: bool

    @property
    def ready_for_model_call(self) -> bool:
        return self.orchestration_key_present


def inspect_environment(values: Mapping[str, str]) -> CredentialReadiness:
    return CredentialReadiness(
        orchestration_key_present=bool(values.get("OPENAI_ORCHESTRATION_API_KEY", "").strip()),
        project_id_present=bool(values.get("OPENAI_ORCHESTRATION_PROJECT_ID", "").strip()),
        admin_key_present=bool(values.get("OPENAI_ADMIN_API_KEY", "").strip()),
        legacy_key_present=bool(values.get("OPENAI_API_KEY", "").strip()),
    )


def inspect_env_file(path: Path) -> CredentialReadiness:
    values: dict[str, str] = {}
    if path.is_file():
        for raw_line in path.read_text(encoding="utf-8").splitlines():
            name, separator, value = raw_line.partition("=")
            if separator and name.strip() in {"OPENAI_ORCHESTRATION_API_KEY", "OPENAI_ORCHESTRATION_PROJECT_ID", "OPENAI_ADMIN_API_KEY", "OPENAI_API_KEY"}:
                values[name.strip()] = value.strip().strip('"').strip("'")
    return inspect_environment(values)
