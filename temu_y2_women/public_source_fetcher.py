from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Callable


Fetcher = Callable[[str], str]
_FETCH_SCHEMA_VERSION = "public-source-fetch-v1"


def fetch_public_source_html(
    source: dict[str, Any],
    fetched_at: str,
    fetcher: Fetcher,
    cache_root: Path,
    artifact_root: Path,
) -> str:
    source_id = str(source["source_id"])
    source_url = str(source["source_url"])
    try:
        html = fetcher(source_url)
    except Exception as error:
        return _fetch_from_cache(source_id, source_url, fetched_at, error, cache_root, artifact_root)
    record = _live_fetch_record(source_id, source_url, fetched_at, html)
    _write_fetch_record(cache_root, source_id, html, record)
    _write_fetch_record(artifact_root, source_id, html, record)
    return html


def _fetch_from_cache(
    source_id: str,
    source_url: str,
    fetched_at: str,
    error: Exception,
    cache_root: Path,
    artifact_root: Path,
) -> str:
    cached = _load_cached_fetch(cache_root, source_id)
    if cached is None:
        raise error
    record = {
        "schema_version": _FETCH_SCHEMA_VERSION,
        "source_id": source_id,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "fetch_status": "cache_fallback",
        "content_sha256": cached["content_sha256"],
        "cache_fetched_at": cached["fetched_at"],
        "error_message": str(error),
    }
    _write_fetch_record(artifact_root, source_id, cached["html"], record)
    return cached["html"]


def _live_fetch_record(source_id: str, source_url: str, fetched_at: str, html: str) -> dict[str, str]:
    return {
        "schema_version": _FETCH_SCHEMA_VERSION,
        "source_id": source_id,
        "source_url": source_url,
        "fetched_at": fetched_at,
        "fetch_status": "live",
        "content_sha256": _content_sha256(html),
    }


def _content_sha256(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()


def _write_fetch_record(root: Path, source_id: str, html: str, record: dict[str, str]) -> None:
    html_path, meta_path = _fetch_paths(root, source_id)
    html_path.parent.mkdir(parents=True, exist_ok=True)
    html_path.write_text(html, encoding="utf-8")
    meta_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_cached_fetch(root: Path, source_id: str) -> dict[str, str] | None:
    html_path, meta_path = _fetch_paths(root, source_id)
    if not html_path.exists() or not meta_path.exists():
        return None
    payload = json.loads(meta_path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        return None
    html = html_path.read_text(encoding="utf-8")
    return {
        "html": html,
        "fetched_at": str(payload.get("fetched_at", "")),
        "content_sha256": str(payload.get("content_sha256", _content_sha256(html))),
    }


def _fetch_paths(root: Path, source_id: str) -> tuple[Path, Path]:
    return root / f"{source_id}.html", root / f"{source_id}.json"
