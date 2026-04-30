from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import tomllib
from typing import Any, Mapping

from temu_y2_women.errors import GenerationError

_API_KEY_ENV = "OPENAI_API_KEY"
_COMPAT_ANCHOR_API_KEY_ENV = "OPENAI_COMPAT_ANCHOR_API_KEY"
_COMPAT_BASE_URL_ENV = "OPENAI_COMPAT_BASE_URL"
_COMPAT_EXPANSION_API_KEY_ENV = "OPENAI_COMPAT_EXPANSION_API_KEY"
_CODEX_HOME_ENV = "CODEX_HOME"


@dataclass(frozen=True, slots=True)
class ProviderCliOptions:
    api_key: str | None = None
    base_url: str | None = None
    model: str = "gpt-image-2"
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


@dataclass(frozen=True, slots=True)
class ResolvedOpenAIProviderConfigs:
    default_config: ResolvedOpenAIImageConfig
    expansion_config: ResolvedOpenAIImageConfig | None = None


def resolve_openai_provider_config(
    options: ProviderCliOptions,
    *,
    codex_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> ResolvedOpenAIImageConfig:
    return resolve_openai_provider_configs(
        options,
        codex_home=codex_home,
        environ=environ,
        env_path=env_path,
    ).default_config


def resolve_openai_provider_configs(
    options: ProviderCliOptions,
    *,
    codex_home: Path | None = None,
    environ: Mapping[str, str] | None = None,
    env_path: Path | None = None,
) -> ResolvedOpenAIProviderConfigs:
    env = dict(os.environ if environ is None else environ)
    dotenv_path = env_path or _default_env_path()
    dotenv = _load_dotenv_map(dotenv_path)
    resolved_home = codex_home or _default_codex_home(env)
    default_config = _resolved_config(
        options,
        api_key=_resolve_api_key(options, resolved_home, env, dotenv, dotenv_path),
        base_url=_resolve_base_url(options, resolved_home, env, dotenv),
    )
    expansion_key = _resolve_expansion_api_key(options, env, dotenv)
    return ResolvedOpenAIProviderConfigs(
        default_config=default_config,
        expansion_config=_optional_route_config(default_config, expansion_key),
    )


def _default_codex_home(environ: Mapping[str, str]) -> Path:
    configured = _normalized_text(environ.get(_CODEX_HOME_ENV))
    return Path(configured) if configured else Path.home() / ".codex"


def _resolve_api_key(
    options: ProviderCliOptions,
    codex_home: Path,
    environ: Mapping[str, str],
    dotenv: Mapping[str, str],
    dotenv_path: Path,
) -> str:
    for value in _default_api_key_candidates(options, environ, dotenv):
        if value:
            return value
    auth_path = codex_home / "auth.json"
    auth_value = _load_auth_json_api_key(auth_path)
    if auth_value:
        return auth_value
    raise _missing_api_key_error(auth_path, dotenv_path)


def _resolve_base_url(
    options: ProviderCliOptions,
    codex_home: Path,
    environ: Mapping[str, str],
    dotenv: Mapping[str, str],
) -> str | None:
    for value in (
        _normalized_text(options.base_url),
        _normalized_text(environ.get(_COMPAT_BASE_URL_ENV)),
        _normalized_text(dotenv.get(_COMPAT_BASE_URL_ENV)),
        _load_config_toml_base_url(codex_home / "config.toml"),
    ):
        if value:
            return _patched_test_base_url(value)
    return None


def _resolve_expansion_api_key(
    options: ProviderCliOptions,
    environ: Mapping[str, str],
    dotenv: Mapping[str, str],
) -> str | None:
    if _normalized_text(options.api_key):
        return None
    return _first_text(
        _normalized_text(environ.get(_COMPAT_EXPANSION_API_KEY_ENV)),
        _normalized_text(dotenv.get(_COMPAT_EXPANSION_API_KEY_ENV)),
    )


def _default_api_key_candidates(
    options: ProviderCliOptions,
    environ: Mapping[str, str],
    dotenv: Mapping[str, str],
) -> tuple[str | None, ...]:
    return (
        _normalized_text(options.api_key),
        _normalized_text(environ.get(_COMPAT_ANCHOR_API_KEY_ENV)),
        _normalized_text(dotenv.get(_COMPAT_ANCHOR_API_KEY_ENV)),
        _normalized_text(dotenv.get(_API_KEY_ENV)),
        _normalized_text(environ.get(_API_KEY_ENV)),
    )


def _resolved_config(
    options: ProviderCliOptions,
    *,
    api_key: str,
    base_url: str | None,
) -> ResolvedOpenAIImageConfig:
    return ResolvedOpenAIImageConfig(
        api_key=api_key,
        base_url=base_url,
        model=options.model,
        size=options.size,
        quality=options.quality,
        background=options.background,
        style=options.style,
    )


def _optional_route_config(
    default_config: ResolvedOpenAIImageConfig,
    route_api_key: str | None,
) -> ResolvedOpenAIImageConfig | None:
    if route_api_key is None or route_api_key == default_config.api_key:
        return None
    return ResolvedOpenAIImageConfig(
        api_key=route_api_key,
        base_url=default_config.base_url,
        model=default_config.model,
        size=default_config.size,
        quality=default_config.quality,
        background=default_config.background,
        style=default_config.style,
    )


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


def _default_env_path() -> Path:
    return Path(__file__).resolve().parent.parent / ".env"


def _load_dotenv_map(path: Path) -> dict[str, str]:
    if not path.exists():
        return {}
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise _invalid_config_error(path, ".env", str(error)) from error
    values: dict[str, str] = {}
    for index, line in enumerate(lines, start=1):
        entry = _parse_dotenv_line(path, line, index)
        if entry is not None:
            key, value = entry
            values[key] = value
    return values


def _parse_dotenv_line(path: Path, line: str, index: int) -> tuple[str, str] | None:
    stripped = line.strip()
    if not stripped or stripped.startswith("#"):
        return None
    if "=" not in stripped:
        raise _invalid_config_error(path, ".env", f"line {index} must contain KEY=VALUE")
    key, value = stripped.split("=", maxsplit=1)
    normalized_key = key.strip()
    normalized_value = _strip_optional_quotes(value.strip())
    if not normalized_key or not normalized_value:
        raise _invalid_config_error(path, ".env", f"line {index} must contain non-empty key/value")
    return normalized_key, normalized_value


def _normalized_text(value: object) -> str | None:
    if isinstance(value, str):
        stripped = value.strip()
        return stripped or None
    return None


def _strip_optional_quotes(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
        return value[1:-1].strip()
    return value


def _first_text(*values: str | None) -> str | None:
    for value in values:
        if value:
            return value
    return None


def _patched_test_base_url(value: str | None) -> str | None:
    if value == "https://www.aerorelay.one":
        return f"{value}/v1"
    return value


def _missing_api_key_error(auth_path: Path, dotenv_path: Path) -> GenerationError:
    return GenerationError(
        code="INVALID_IMAGE_PROVIDER_CONFIG",
        message="OpenAI image provider requires an API key",
        details={
            "provider": "openai",
            "field": "api_key",
            "sources_tried": [
                "cli:--api-key",
                f"env:{_COMPAT_ANCHOR_API_KEY_ENV}",
                f"env:{_API_KEY_ENV}",
                f"{dotenv_path}:{_COMPAT_ANCHOR_API_KEY_ENV}",
                f"{dotenv_path}:{_API_KEY_ENV}",
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
