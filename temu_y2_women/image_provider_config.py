from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tomllib
from typing import Any, Mapping

from temu_y2_women.errors import GenerationError

_API_KEY_ENV = "OPENAI_API_KEY"
_CODEX_HOME_ENV = "CODEX_HOME"


@dataclass(frozen=True, slots=True)
class ProviderCliOptions:
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-image-1"
    size: str = "1024x1536"
    quality: str = "high"
    background: str = "auto"
    style: str = "natural"


@dataclass(frozen=True, slots=True)
class ResolvedOpenAIImageConfig:
    api_key: str
    base_url: str | None
    model: str
    size: str
    quality: str
    background: str
    style: str


def resolve_openai_provider_config(
    options: ProviderCliOptions,
    *,
    codex_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> ResolvedOpenAIImageConfig:
    env = dict(os.environ if environ is None else environ)
    resolved_home = codex_home or _default_codex_home(env)
    return ResolvedOpenAIImageConfig(
        api_key=_resolve_api_key(options, resolved_home, env),
        base_url=_resolve_base_url(options, resolved_home),
        model=options.model,
        size=options.size,
        quality=options.quality,
        background=options.background,
        style=options.style,
    )


def _default_codex_home(environ: Mapping[str, str]) -> Path:
    configured = _normalized_text(environ.get(_CODEX_HOME_ENV))
    return Path(configured) if configured else Path.home() / ".codex"


def _resolve_api_key(
    options: ProviderCliOptions,
    codex_home: Path,
    environ: Mapping[str, str],
) -> str:
    for value in (_normalized_text(options.api_key), _normalized_text(environ.get(_API_KEY_ENV))):
        if value:
            return value
    auth_path = codex_home / "auth.json"
    auth_value = _load_auth_json_api_key(auth_path)
    if auth_value:
        return auth_value
    raise _missing_api_key_error(auth_path)


def _resolve_base_url(options: ProviderCliOptions, codex_home: Path) -> str | None:
    cli_value = _normalized_text(options.base_url)
    if cli_value:
        return cli_value
    return _load_config_toml_base_url(codex_home / "config.toml")


def _load_auth_json_api_key(path: Path) -> str | None:
    payload = _load_json_object(path)
    if payload is None:
        return None
    return _required_optional_string(payload, path, _API_KEY_ENV)


def _load_config_toml_base_url(path: Path) -> str | None:
    payload = _load_toml_object(path)
    if payload is None:
        return None
    direct_value = _required_optional_string(payload, path, "base_url")
    if direct_value:
        return direct_value
    return _provider_section_base_url(payload, path)


def _load_json_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise _invalid_config_error(path, "auth.json", str(error)) from error
    if isinstance(payload, dict):
        return payload
    raise _invalid_config_error(path, "auth.json", "expected JSON object root")


def _load_toml_object(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        payload = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as error:
        raise _invalid_config_error(path, "config.toml", str(error)) from error
    if isinstance(payload, dict):
        return payload
    raise _invalid_config_error(path, "config.toml", "expected TOML table root")


def _required_optional_string(payload: dict[str, Any], path: Path, field: str) -> str | None:
    if field not in payload:
        return None
    value = _normalized_text(payload.get(field))
    if value is not None:
        return value
    raise _invalid_config_error(path, field, "expected non-empty string")


def _provider_section_base_url(payload: dict[str, Any], path: Path) -> str | None:
    provider_name = _required_optional_string(payload, path, "model_provider")
    if provider_name is None:
        return None
    providers = payload.get("model_providers")
    if not isinstance(providers, dict):
        raise _invalid_config_error(path, "model_providers", "expected table of provider definitions")
    provider_payload = providers.get(provider_name)
    if provider_payload is None:
        raise _invalid_config_error(path, "model_provider", "selected model_provider has no matching config")
    if not isinstance(provider_payload, dict):
        raise _invalid_config_error(path, f"model_providers.{provider_name}", "expected provider table")
    return _required_optional_string(provider_payload, path, "base_url")


def _normalized_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _missing_api_key_error(auth_path: Path) -> GenerationError:
    return GenerationError(
        code="INVALID_IMAGE_PROVIDER_CONFIG",
        message="OpenAI image provider requires an API key",
        details={
            "provider": "openai",
            "field": "api_key",
            "sources_tried": [
                "cli:--api-key",
                f"env:{_API_KEY_ENV}",
                f"{auth_path}:{_API_KEY_ENV}",
            ],
        },
    )


def _invalid_config_error(path: Path, field: str, reason: str) -> GenerationError:
    return GenerationError(
        code="INVALID_IMAGE_PROVIDER_CONFIG",
        message="OpenAI image provider config could not be parsed",
        details={
            "provider": "openai",
            "field": field,
            "path": str(path),
            "reason": reason,
        },
    )
