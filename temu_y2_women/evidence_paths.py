from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

_DEFAULT_DATA_ROOT = Path(__file__).resolve().parent.parent / "data" / "mvp" / "dress"


@dataclass(frozen=True, slots=True)
class EvidencePaths:
    elements_path: Path
    strategies_path: Path
    taxonomy_path: Path
    style_families_path: Path | None = None

    @classmethod
    def defaults(cls) -> "EvidencePaths":
        return cls(
            elements_path=_DEFAULT_DATA_ROOT / "elements.json",
            strategies_path=_DEFAULT_DATA_ROOT / "strategy_templates.json",
            taxonomy_path=_DEFAULT_DATA_ROOT / "evidence_taxonomy.json",
            style_families_path=_DEFAULT_DATA_ROOT / "style_families.json",
        )
