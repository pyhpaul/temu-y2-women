from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

from temu_y2_women.errors import GenerationError
from temu_y2_women.evidence_repository import load_evidence_taxonomy


_DEFAULT_TAXONOMY_PATH = Path("data/mvp/dress/evidence_taxonomy.json")
_SNAPSHOT_SCHEMA_VERSION = "public-source-snapshot-v1"
_CANONICAL_SCHEMA_VERSION = "canonical-signals-v1"
_ALLOWED_PRICE_BANDS = {"low", "mid", "high"}
_ALLOWED_SIGNAL_STATUS = {"active"}
_ALLOWED_PRICE_BAND_RESOLUTION = {"observed", "source_default", "rule_fallback"}
_SOURCE_PROFILES = {
    "whowhatwear-summer-2025-dress-trends": {
        "adapter_version": "whowhatwear_editorial_v1",
        "section_confidence": {
            "the-vacation-mini": 0.78,
            "fairy-sleeves": 0.74,
            "all-things-polka-dots": 0.68,
            "the-exaggerated-drop-waist": 0.70,
            "sheer-printed-midis": 0.69,
        },
        "evidence_rules": (
            {
                "keywords": ("smocked bodices", "halter ties", "prints", "vacation mini"),
                "manual_tags": ("vacation",),
                "excerpt_anchor": "smocked bodices",
            },
            {
                "keywords": ("fairy sleeves", "fluttery", "romance"),
                "manual_tags": ("airy", "romantic"),
                "excerpt_anchor": "soft, fluttery",
            },
            {
                "keywords": ("polka dots", "micro-dot", "dotted dress"),
                "manual_tags": (),
                "excerpt_anchor": "whether you go micro-dot",
            },
            {
                "keywords": ("drop-waist dresses", "dramatic volume", "structure"),
                "manual_tags": (),
                "excerpt_anchor": "drop-waist dresses",
            },
            {
                "keywords": ("sheer", "soft printed dresses", "playful and polished"),
                "manual_tags": ("airy",),
                "excerpt_anchor": "soft printed dresses",
            },
        ),
    },
    "whowhatwear-summer-dress-trends-2025": {
        "adapter_version": "whowhatwear_editorial_v1",
        "section_confidence": {
            "shirred-bodices": 0.74,
            "drop-waist": 0.76,
            "elegant-bandeaus": 0.69,
            "chic-stripes": 0.68,
            "romantic-sleeves": 0.71,
            "bubble-hems": 0.66,
            "lingerie-slips": 0.67,
            "halterneck-dresses": 0.72,
        },
        "evidence_rules": (
            {
                "keywords": ("shirred dress trend", "smocked bodices", "shirring"),
                "manual_tags": ("feminine",),
                "excerpt_anchor": "shirred dress trend",
            },
            {
                "keywords": ("drop-waist dress trend", "drop-waist", "lengthened effect"),
                "manual_tags": ("feminine",),
                "excerpt_anchor": "drop-waist dress trend",
            },
            {
                "keywords": ("absence of straps", "bustiers", "bandeau dress"),
                "manual_tags": ("party",),
                "excerpt_anchor": "absence of straps",
            },
            {
                "keywords": ("stripes", "neapolitan", "discrete lines"),
                "manual_tags": (),
                "excerpt_anchor": "stripes have rightfully earned",
            },
            {
                "keywords": ("romantic", "puff sleeves", "broderie anglaise"),
                "manual_tags": ("romantic",),
                "excerpt_anchor": "romantic, dreamy takes",
            },
            {
                "keywords": ("bubble-hem trend", "bubble hems"),
                "manual_tags": (),
                "excerpt_anchor": "bubble-hem trend",
            },
            {
                "keywords": ("slip dresses", "open button-down shirt", "summer aesthetic"),
                "manual_tags": (),
                "excerpt_anchor": "slip dresses will never go out of style",
            },
            {
                "keywords": ("halter neck trend", "halterneck", "in-demand trends"),
                "manual_tags": (),
                "excerpt_anchor": "halter neck trend",
            },
        ),
    },
    "marieclaire-summer-2025-dress-trends": {
        "adapter_version": "marieclaire_editorial_v1",
        "section_confidence": {
            "linen-dresses": 0.71,
            "smocked-dresses": 0.76,
            "chocolate-brown-dresses": 0.67,
            "polka-dot-dresses": 0.72,
            "gingham-dresses": 0.70,
            "boho-dresses": 0.75,
            "babydoll-dresses": 0.69,
        },
        "evidence_rules": (
            {
                "keywords": ("linen dresses", "summer wardrobe", "mid-summer refresh"),
                "manual_tags": ("lightweight",),
                "excerpt_anchor": "linen dresses are fundamental",
            },
            {
                "keywords": ("smocked dresses", "throw-on-and-go", "hottest days"),
                "manual_tags": (),
                "excerpt_anchor": "smocked dresses have quietly saved",
            },
            {
                "keywords": ("chocolate brown", "summer neutral shade", "comfort zone"),
                "manual_tags": (),
                "excerpt_anchor": "chocolate brown is making a strong case",
            },
            {
                "keywords": ("polka dot", "it-print", "strong comeback"),
                "manual_tags": (),
                "excerpt_anchor": "polka dot is summer's it-print",
            },
            {
                "keywords": ("gingham", "major print trend", "must-buy status"),
                "manual_tags": (),
                "excerpt_anchor": "major print trend for the season",
            },
            {
                "keywords": ("boho fashion trend", "floaty silhouettes", "sheer fabrics"),
                "manual_tags": ("airy", "romantic"),
                "excerpt_anchor": "boho fashion trend is going strong",
            },
            {
                "keywords": ("babydoll silhouette", "low-key days", "heat waves"),
                "manual_tags": (),
                "excerpt_anchor": "rise of the babydoll silhouette",
            },
        ),
    },
}
_CANONICAL_SIGNAL_REQUIRED_FIELDS = {
    "canonical_signal_id",
    "source_id",
    "source_type",
    "source_url",
    "captured_at",
    "fetched_at",
    "target_market",
    "category",
    "title",
    "summary",
    "evidence_excerpt",
    "observed_price_band",
    "price_band_resolution",
    "observed_occasion_tags",
    "observed_season_tags",
    "manual_tags",
    "status",
    "extraction_provenance",
}


def build_canonical_signals(snapshot: dict[str, Any], default_price_band: str) -> dict[str, Any]:
    _validate_snapshot(snapshot)
    if default_price_band not in _ALLOWED_PRICE_BANDS:
        raise _builder_error("default_price_band", "unsupported default price band")
    sections = [_validate_section(section, index) for index, section in enumerate(snapshot["sections"])]
    signals = [_build_canonical_signal(snapshot, section, default_price_band, index) for index, section in enumerate(sections, start=1)]
    return {"schema_version": _CANONICAL_SCHEMA_VERSION, "signals": signals}


def build_signal_bundle(canonical_payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(canonical_payload, dict):
        raise _builder_error("signals", "canonical signals payload must be an object")
    if canonical_payload.get("schema_version") != _CANONICAL_SCHEMA_VERSION:
        raise _builder_error("schema_version", "unsupported canonical signals schema version")
    signals = canonical_payload.get("signals")
    if not isinstance(signals, list) or not signals:
        raise _builder_error("signals", "canonical signals payload must contain non-empty signals")
    validated = [_validate_canonical_signal(signal, index) for index, signal in enumerate(signals)]
    return {"schema_version": "signal-bundle-v1", "signals": [_build_signal_bundle_record(signal) for signal in validated]}


def _build_canonical_signal(
    snapshot: dict[str, Any],
    section: dict[str, Any],
    default_price_band: str,
    index: int,
) -> dict[str, Any]:
    profile = _optional_source_profile(str(snapshot["source_id"]))
    evidence_rules = _profile_evidence_rules(profile)
    evidence_excerpt, matched_keywords = _derive_evidence(section, evidence_rules)
    return {
        "canonical_signal_id": f"{snapshot['source_id']}-{section['section_id']}-{index:03d}",
        "source_id": snapshot["source_id"],
        "source_type": snapshot["source_type"],
        "source_url": snapshot["source_url"],
        "captured_at": snapshot["captured_at"],
        "fetched_at": snapshot["fetched_at"],
        "target_market": snapshot["target_market"],
        "category": snapshot["category"],
        "title": section["heading"],
        "summary": section["text"],
        "evidence_excerpt": evidence_excerpt,
        "observed_occasion_tags": _derive_occasion_tags(section),
        "observed_season_tags": _derive_season_tags(section),
        "manual_tags": _derive_manual_tags(section, matched_keywords, evidence_rules),
        "observed_price_band": default_price_band,
        "price_band_resolution": "source_default",
        "status": "active",
        "extraction_provenance": _build_provenance(section, matched_keywords, profile),
    }


def _derive_evidence(section: dict[str, Any], evidence_rules: tuple[dict[str, Any], ...]) -> tuple[str, list[str]]:
    metadata = _section_evidence_metadata(section)
    if metadata is not None:
        return metadata
    rule = _best_evidence_rule(section, evidence_rules)
    if rule is None:
        return _default_excerpt(str(section["text"])), []
    matched_keywords = _matched_keywords(rule, _section_corpus(section))
    excerpt = _excerpt_from_text(str(section["text"]), str(rule["excerpt_anchor"]))
    return excerpt, matched_keywords


def _section_evidence_metadata(section: dict[str, Any]) -> tuple[str, list[str]] | None:
    matched_keywords = _optional_string_list(section, "matched_keywords")
    excerpt_anchor = _optional_string(section, "excerpt_anchor")
    if matched_keywords is None and excerpt_anchor is None:
        return None
    excerpt = _excerpt_from_text(str(section["text"]), excerpt_anchor) if excerpt_anchor else _default_excerpt(str(section["text"]))
    return excerpt, matched_keywords or []


def _best_evidence_rule(
    section: dict[str, Any],
    evidence_rules: tuple[dict[str, Any], ...],
) -> dict[str, Any] | None:
    corpus = _section_corpus(section)
    best_rule: dict[str, Any] | None = None
    best_score = 0
    for rule in evidence_rules:
        score = len(_matched_keywords(rule, corpus))
        if score > best_score:
            best_rule = dict(rule)
            best_score = score
    return best_rule


def _matched_keywords(rule: dict[str, Any], corpus: str) -> list[str]:
    return [keyword for keyword in list(rule["keywords"]) if _normalize_text(keyword) in corpus]


def _section_corpus(section: dict[str, Any]) -> str:
    return _normalize_text(f"{section['heading']} {section['text']}")


def _excerpt_from_text(text: str, anchor: str) -> str:
    casefold_anchor = anchor.casefold().strip()
    for sentence in _split_sentences(text):
        direct_index = sentence.casefold().find(casefold_anchor)
        if direct_index >= 0:
            return sentence[direct_index:].strip().rstrip(".!?")
        normalized_anchor = _normalize_text(anchor)
        index = _normalize_text(sentence).find(normalized_anchor)
        if index >= 0:
            return sentence[index:].strip().rstrip(".!?")
    return _default_excerpt(text)


def _default_excerpt(text: str) -> str:
    sentences = _split_sentences(text)
    return sentences[0].strip().rstrip(".!?") if sentences else text.strip().rstrip(".!?")


def _split_sentences(text: str) -> list[str]:
    return [item for item in re.split(r"(?<=[.!?])\s+", text.strip()) if item]


def _derive_occasion_tags(section: dict[str, Any]) -> list[str]:
    return _supported_source_tags(list(section["tags"]), "allowed_occasions")


def _derive_season_tags(section: dict[str, Any]) -> list[str]:
    return _supported_source_tags(list(section["tags"]), "allowed_seasons")


def _derive_manual_tags(
    section: dict[str, Any],
    matched_keywords: list[str],
    evidence_rules: tuple[dict[str, Any], ...],
) -> list[str]:
    values = [
        *_supported_source_tags(list(section["tags"]), "allowed_tags"),
        *_manual_tags_from_keywords(matched_keywords, evidence_rules),
    ]
    return _validated_tags(values, "allowed_tags", "manual_tags")


def _manual_tags_from_keywords(
    matched_keywords: list[str],
    evidence_rules: tuple[dict[str, Any], ...],
) -> list[str]:
    values: list[str] = []
    matched = set(matched_keywords)
    for rule in evidence_rules:
        if matched.intersection(rule["keywords"]):
            values.extend(list(rule["manual_tags"]))
    return values


def _optional_source_profile(source_id: str) -> dict[str, Any] | None:
    return _SOURCE_PROFILES.get(source_id)


def _profile_evidence_rules(profile: dict[str, Any] | None) -> tuple[dict[str, Any], ...]:
    if profile is None:
        return ()
    return tuple(profile["evidence_rules"])


def _section_confidence(profile: dict[str, Any] | None, section: dict[str, Any]) -> float:
    value = section.get("confidence")
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return float(value)
    if profile is None:
        return 0.65
    return profile["section_confidence"].get(str(section["section_id"]), 0.65)


def _build_provenance(
    section: dict[str, Any],
    matched_keywords: list[str],
    profile: dict[str, Any] | None,
) -> dict[str, Any]:
    return {
        "source_section": str(section["section_id"]),
        "matched_keywords": matched_keywords,
        "adapter_version": _optional_string(section, "adapter_version") or _profile_adapter_version(profile),
        "warnings": _optional_string_list(section, "warnings") or ["price band defaulted from source registry"],
        "confidence": _section_confidence(profile, section),
    }


def _profile_adapter_version(profile: dict[str, Any] | None) -> str:
    if profile is None:
        return "configured_editorial_v1"
    return str(profile["adapter_version"])


def _build_signal_bundle_record(signal: dict[str, Any]) -> dict[str, Any]:
    return {
        "signal_id": signal["canonical_signal_id"],
        "source_type": signal["source_type"],
        "source_url": signal["source_url"],
        "captured_at": signal["captured_at"],
        "target_market": signal["target_market"],
        "category": signal["category"],
        "title": signal["title"],
        "summary": signal["summary"],
        "observed_price_band": signal["observed_price_band"],
        "observed_occasion_tags": list(signal["observed_occasion_tags"]),
        "observed_season_tags": list(signal["observed_season_tags"]),
        "manual_tags": list(signal["manual_tags"]),
        "status": signal["status"],
        "extraction_provenance": dict(signal["extraction_provenance"]),
    }


@lru_cache(maxsize=1)
def _signal_taxonomy() -> dict[str, Any]:
    return load_evidence_taxonomy(_DEFAULT_TAXONOMY_PATH)


def _supported_source_tags(values: list[str], taxonomy_field: str) -> list[str]:
    lookup = _taxonomy_lookup(taxonomy_field)
    supported: list[str] = []
    for value in values:
        canonical = lookup.get(_normalize_text(value))
        if canonical and canonical not in supported:
            supported.append(canonical)
    return supported


def _validated_tags(values: list[str], taxonomy_field: str, field: str) -> list[str]:
    tags = _dedupe(values)
    lookup = _taxonomy_lookup(taxonomy_field)
    invalid = [tag for tag in tags if _normalize_text(tag) not in lookup]
    if invalid:
        raise _builder_error(field, f"unsupported {field} metadata values: {invalid}")
    return [lookup[_normalize_text(tag)] for tag in tags]


def _taxonomy_lookup(taxonomy_field: str) -> dict[str, str]:
    return {_normalize_text(value): value for value in list(_signal_taxonomy()[taxonomy_field])}


def _validate_snapshot(snapshot: dict[str, Any]) -> None:
    _require_mapping(snapshot, "snapshot")
    if snapshot.get("schema_version") != _SNAPSHOT_SCHEMA_VERSION:
        raise _builder_error("snapshot.schema_version", "unsupported raw source snapshot schema version")
    for field in ("source_id", "source_type", "source_url", "captured_at", "fetched_at", "target_market", "category"):
        _require_string_field(snapshot, field, f"snapshot.{field}")
    sections = snapshot.get("sections")
    if not isinstance(sections, list) or not sections:
        raise _builder_error("sections", "raw source snapshot must contain non-empty sections")


def _validate_section(section: Any, index: int) -> dict[str, Any]:
    _require_mapping(section, f"section[{index}]")
    _require_string_field(section, "section_id", "section.section_id")
    _require_string_field(section, "heading", "section.heading")
    _require_string_field(section, "text", "section.text")
    _require_string_list(section, "tags", "section.tags")
    _validate_optional_section_metadata(section)
    return dict(section)


def _validate_optional_section_metadata(section: dict[str, Any]) -> None:
    _require_optional_string_list(section, "matched_keywords", "section.matched_keywords")
    _require_optional_string_field(section, "excerpt_anchor", "section.excerpt_anchor")
    _require_optional_string_field(section, "adapter_version", "section.adapter_version")
    _require_optional_string_list(section, "warnings", "section.warnings")
    value = section.get("confidence")
    if value is None or isinstance(value, (int, float)) and not isinstance(value, bool):
        return
    raise _builder_error("section.confidence", "section.confidence must be numeric")


def _validate_canonical_signal(signal: Any, index: int) -> dict[str, Any]:
    _require_mapping(signal, f"signal[{index}]")
    missing = sorted(_CANONICAL_SIGNAL_REQUIRED_FIELDS.difference(signal.keys()))
    if missing:
        raise _builder_error(f"signal.{missing[0]}", "canonical signal record is missing required fields")
    for field in (
        "canonical_signal_id",
        "source_id",
        "source_type",
        "source_url",
        "captured_at",
        "fetched_at",
        "target_market",
        "category",
        "title",
        "summary",
        "evidence_excerpt",
        "observed_price_band",
        "price_band_resolution",
        "status",
    ):
        _require_string_field(signal, field, f"signal.{field}")
    for field in ("observed_occasion_tags", "observed_season_tags", "manual_tags"):
        _require_string_list(signal, field, f"signal.{field}")
    if signal["observed_price_band"] not in _ALLOWED_PRICE_BANDS:
        raise _builder_error("signal.observed_price_band", "unsupported canonical signal observed_price_band")
    if signal["price_band_resolution"] not in _ALLOWED_PRICE_BAND_RESOLUTION:
        raise _builder_error("signal.price_band_resolution", "unsupported canonical signal price_band_resolution")
    if signal["status"] not in _ALLOWED_SIGNAL_STATUS:
        raise _builder_error("signal.status", "unsupported canonical signal status")
    _validate_provenance(signal["extraction_provenance"])
    return dict(signal)


def _validate_provenance(provenance: Any) -> None:
    _require_mapping(provenance, "signal.extraction_provenance")
    _require_string_field(provenance, "source_section", "signal.extraction_provenance.source_section")
    _require_string_list(provenance, "matched_keywords", "signal.extraction_provenance.matched_keywords")
    _require_string_field(provenance, "adapter_version", "signal.extraction_provenance.adapter_version")
    _require_string_list(provenance, "warnings", "signal.extraction_provenance.warnings")
    confidence = provenance.get("confidence")
    if isinstance(confidence, bool):
        raise _builder_error("signal.extraction_provenance.confidence", "signal.extraction_provenance.confidence must be numeric")
    if isinstance(confidence, (int, float)):
        return
    raise _builder_error("signal.extraction_provenance.confidence", "signal.extraction_provenance.confidence must be numeric")


def _require_mapping(value: Any, field: str) -> None:
    if isinstance(value, dict):
        return
    raise _builder_error(field, f"{field} must be an object")


def _require_string_field(record: dict[str, Any], field: str, error_field: str) -> None:
    if isinstance(record.get(field), str):
        return
    raise _builder_error(error_field, f"{error_field} must be a string")


def _require_string_list(record: dict[str, Any], field: str, error_field: str) -> None:
    value = record.get(field)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    raise _builder_error(error_field, f"{error_field} must be a list of strings")


def _require_optional_string_field(record: dict[str, Any], field: str, error_field: str) -> None:
    value = record.get(field)
    if value is None or isinstance(value, str):
        return
    raise _builder_error(error_field, f"{error_field} must be a string")


def _require_optional_string_list(record: dict[str, Any], field: str, error_field: str) -> None:
    value = record.get(field)
    if value is None or isinstance(value, list) and all(isinstance(item, str) for item in value):
        return
    raise _builder_error(error_field, f"{error_field} must be a list of strings")


def _normalize_text(value: str) -> str:
    return " ".join(value.strip().casefold().split())


def _optional_string(section: dict[str, Any], field: str) -> str | None:
    value = section.get(field)
    return value if isinstance(value, str) and value.strip() else None


def _optional_string_list(section: dict[str, Any], field: str) -> list[str] | None:
    value = section.get(field)
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return [item for item in value if item.strip()]
    return None


def _dedupe(values: list[str]) -> list[str]:
    ordered: list[str] = []
    for value in values:
        if value not in ordered:
            ordered.append(value)
    return ordered


def _builder_error(field: str, message: str) -> GenerationError:
    return GenerationError(
        code="INVALID_CANONICAL_SIGNAL_INPUT",
        message=message,
        details={"field": field},
    )
