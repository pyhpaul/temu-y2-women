# Public Roundup Image Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a public roundup/list-page refresh path that extracts product cards, observes objective dress slots from card images, aggregates repeated slot/value evidence into page-level canonical signals, and feeds the existing ingestion pipeline without mutating active evidence.

**Architecture:** Keep the existing editorial-text refresh contract intact, but extend the registry with explicit pipeline routing and add a second source path for roundup image cards. Split the new behavior into three focused units: a roundup page adapter that only extracts cards, a card observer contract plus live OpenAI-compatible implementation, and a roundup canonical builder that turns repeated card observations into page-level canonical signals before rejoining the existing `signal bundle -> signal_ingestion` path.

**Tech Stack:** Python 3 standard library, `unittest`, JSON fixtures, existing `GenerationError`, existing `public_signal_refresh` / `canonical_signal_builder` / `signal_ingestion` modules, OpenAI Python SDK for the live observer.

**Execution Note:** This plan implements image observation only. It does not add any `gpt-image-2` render fallback. Project-level policy is now strict edit-only: use `/v1/images/edits` for reference-image edit/expansion work, and if edits are unavailable or fail, return the error directly instead of switching to `/v1/images/generations`.

---

## File Map

- Modify: `data/refresh/dress/source_registry.json`
  - Add one roundup source entry and the new routing/config fields.
- Modify: `temu_y2_women/public_source_registry.py`
  - Validate `pipeline_mode`, roundup source types, `card_limit`, `aggregation_threshold`, and `observation_model`.
- Modify: `temu_y2_women/public_source_adapter.py`
  - Register a roundup adapter ID.
- Create: `temu_y2_women/public_source_adapters/whowhatwear_roundup.py`
  - Parse roundup/list-page HTML into a roundup snapshot with card records.
- Create: `temu_y2_women/public_card_observer.py`
  - Define the card-observation contract, whitelist validation, and deterministic batch observation helper.
- Create: `temu_y2_women/public_card_observer_openai.py`
  - Implement the live OpenAI-compatible card observer used outside tests.
- Create: `temu_y2_women/roundup_canonical_signal_builder.py`
  - Aggregate repeated card observations into page-level `canonical-signals-v1`.
- Modify: `temu_y2_women/public_signal_refresh.py`
  - Route by `pipeline_mode`, write `card_observations` artifacts, and merge roundup canonical signals with editorial canonical signals.
- Modify: `tests/test_public_source_registry.py`
  - Cover new registry fields and validation errors.
- Modify: `tests/test_public_source_adapter.py`
  - Cover roundup adapter resolution and snapshot parsing.
- Create: `tests/test_public_card_observer.py`
  - Cover whitelist-only observations, abstain handling, and `card_limit`.
- Create: `tests/test_public_card_observer_openai.py`
  - Cover live observer request building and response parsing without network calls.
- Create: `tests/test_roundup_canonical_signal_builder.py`
  - Cover page-level aggregation thresholds and `supporting_card_ids`.
- Modify: `tests/test_public_signal_refresh.py`
  - Cover mixed editorial + roundup refresh runs and new report/artifact fields.
- Create: `tests/fixtures/public_sources/dress/whowhatwear-best-summer-dresses-2025.html`
  - Synthetic roundup/list-page fixture with three product cards.
- Create: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json`
  - Expected roundup snapshot.
- Create: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-card-observations.json`
  - Expected card observations produced by the fake observer.
- Create: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`
  - Expected page-level aggregated canonical signals.
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`
  - Expand the report to include roundup source detail fields after mixed-source integration.

### Task 1: Add roundup source routing and HTML-to-card snapshot parsing

**Files:**
- Modify: `data/refresh/dress/source_registry.json`
- Modify: `temu_y2_women/public_source_registry.py`
- Modify: `temu_y2_women/public_source_adapter.py`
- Create: `temu_y2_women/public_source_adapters/whowhatwear_roundup.py`
- Modify: `tests/test_public_source_registry.py`
- Modify: `tests/test_public_source_adapter.py`
- Create: `tests/fixtures/public_sources/dress/whowhatwear-best-summer-dresses-2025.html`
- Create: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json`

- [ ] **Step 1: Write the failing registry + roundup adapter tests and fixtures**

Append these tests to `tests/test_public_source_registry.py`:

```python
    def test_load_enabled_sources_returns_roundup_routing_fields(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        result = load_public_source_registry(Path("data/refresh/dress/source_registry.json"))

        roundup = next(source for source in result if source["source_id"] == "whowhatwear-best-summer-dresses-2025")
        self.assertEqual(roundup["pipeline_mode"], "roundup_image_cards")
        self.assertEqual(roundup["card_limit"], 12)
        self.assertEqual(roundup["aggregation_threshold"], 2)
        self.assertEqual(roundup["observation_model"], "gpt-4.1-mini")

    def test_registry_rejects_invalid_roundup_pipeline_fields(self) -> None:
        from temu_y2_women.public_source_registry import load_public_source_registry

        payload = {
            "schema_version": "public-source-registry-v1",
            "sources": [
                {
                    "source_id": "bad-roundup",
                    "source_type": "public_roundup_web",
                    "source_url": "https://example.com/roundup",
                    "target_market": "US",
                    "category": "dress",
                    "fetch_mode": "html",
                    "adapter_id": "whowhatwear_roundup_v1",
                    "default_price_band": "mid",
                    "pipeline_mode": "roundup_image_cards",
                    "card_limit": 0,
                    "aggregation_threshold": 0,
                    "observation_model": "",
                    "priority": 80,
                    "weight": 0.8,
                    "enabled": True,
                }
            ],
        }
        with TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "registry.json"
            path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(Exception, "card_limit|aggregation_threshold|observation_model"):
                load_public_source_registry(path)
```

Append these tests to `tests/test_public_source_adapter.py`:

```python
    def test_resolve_public_source_adapter_returns_roundup_parser(self) -> None:
        from temu_y2_women.public_source_adapter import resolve_public_source_adapter
        from temu_y2_women.public_source_adapters.whowhatwear_roundup import parse_whowhatwear_roundup_html

        self.assertIs(resolve_public_source_adapter("whowhatwear_roundup_v1"), parse_whowhatwear_roundup_html)

    def test_parse_whowhatwear_roundup_html_returns_expected_snapshot(self) -> None:
        from temu_y2_women.public_source_adapters.whowhatwear_roundup import parse_whowhatwear_roundup_html

        html = (_FIXTURE_DIR / "whowhatwear-best-summer-dresses-2025.html").read_text(encoding="utf-8")
        source = {
            "source_id": "whowhatwear-best-summer-dresses-2025",
            "source_type": "public_roundup_web",
            "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
            "target_market": "US",
            "category": "dress",
            "pipeline_mode": "roundup_image_cards",
            "card_limit": 12,
            "aggregation_threshold": 2,
            "observation_model": "gpt-4.1-mini",
        }

        result = parse_whowhatwear_roundup_html(source=source, html=html, fetched_at="2026-04-28T00:00:00Z")

        expected = json.loads(
            (_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(result, expected)
```

Create `tests/fixtures/public_sources/dress/whowhatwear-best-summer-dresses-2025.html` with this exact HTML:

```html
<html>
  <head>
    <title>Best Summer Dresses 2025</title>
    <meta property="article:published_time" content="2025-06-20T07:00:00Z" />
  </head>
  <body>
    <h1>Best Summer Dresses 2025</h1>
    <ul data-roundup-cards="dresses">
      <li data-card>
        <a href="https://shop.example.com/products/white-mini-dress" data-card-link>
          <img src="https://images.example.com/white-mini-dress.jpg" alt="White mini dress" />
          <span data-card-title>White Mini Dress</span>
        </a>
        <span data-card-brand>Example Brand</span>
      </li>
      <li data-card>
        <a href="https://shop.example.com/products/polka-dot-mini-dress" data-card-link>
          <img src="https://images.example.com/polka-dot-mini-dress.jpg" alt="Polka-dot mini dress" />
          <span data-card-title>Polka-Dot Mini Dress</span>
        </a>
        <span data-card-brand>Example Brand</span>
      </li>
      <li data-card>
        <a href="https://shop.example.com/products/drop-waist-midi-dress" data-card-link>
          <img src="https://images.example.com/drop-waist-midi-dress.jpg" alt="Drop-waist midi dress" />
          <span data-card-title>Drop-Waist Midi Dress</span>
        </a>
        <span data-card-brand>Another Brand</span>
      </li>
    </ul>
  </body>
</html>
```

Create `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json`:

```json
{
  "schema_version": "public-roundup-source-snapshot-v1",
  "source_id": "whowhatwear-best-summer-dresses-2025",
  "source_type": "public_roundup_web",
  "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
  "captured_at": "2025-06-20",
  "fetched_at": "2026-04-28T00:00:00Z",
  "target_market": "US",
  "category": "dress",
  "page_title": "Best Summer Dresses 2025",
  "page_context_tags": ["summer", "shopping", "dress"],
  "cards": [
    {
      "card_id": "whowhatwear-best-summer-dresses-2025-card-001",
      "rank": 1,
      "title": "White Mini Dress",
      "image_url": "https://images.example.com/white-mini-dress.jpg",
      "source_url": "https://shop.example.com/products/white-mini-dress",
      "price_text": "",
      "brand_text": "Example Brand",
      "badges": []
    },
    {
      "card_id": "whowhatwear-best-summer-dresses-2025-card-002",
      "rank": 2,
      "title": "Polka-Dot Mini Dress",
      "image_url": "https://images.example.com/polka-dot-mini-dress.jpg",
      "source_url": "https://shop.example.com/products/polka-dot-mini-dress",
      "price_text": "",
      "brand_text": "Example Brand",
      "badges": []
    },
    {
      "card_id": "whowhatwear-best-summer-dresses-2025-card-003",
      "rank": 3,
      "title": "Drop-Waist Midi Dress",
      "image_url": "https://images.example.com/drop-waist-midi-dress.jpg",
      "source_url": "https://shop.example.com/products/drop-waist-midi-dress",
      "price_text": "",
      "brand_text": "Another Brand",
      "badges": []
    }
  ],
  "warnings": []
}
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python -m unittest tests.test_public_source_registry tests.test_public_source_adapter -v
```

Expected:
- `FAIL` because the registry does not yet accept roundup routing fields
- `FAIL` because `whowhatwear_roundup_v1` is not yet registered

- [ ] **Step 3: Implement registry validation and roundup snapshot parsing**

Modify `temu_y2_women/public_source_registry.py` to add roundup support:

```python
_SUPPORTED_SOURCE_TYPES = {"public_editorial_web", "public_roundup_web"}
_SUPPORTED_PIPELINE_MODES = {"editorial_text", "roundup_image_cards"}


def _required_fields() -> set[str]:
    return {
        "source_id",
        "source_type",
        "source_url",
        "target_market",
        "category",
        "fetch_mode",
        "adapter_id",
        "default_price_band",
        "pipeline_mode",
        "priority",
        "weight",
        "enabled",
    }


def _validate_source_record(path: Path, index: int, source: Any, seen_ids: set[str]) -> dict[str, Any]:
    ...
    _require_allowed(path, index, source, "pipeline_mode", _SUPPORTED_PIPELINE_MODES)
    if source["pipeline_mode"] == "roundup_image_cards":
        _require_positive_int(path, index, source, "card_limit")
        _require_positive_int(path, index, source, "aggregation_threshold")
        _require_string(path, index, source, "observation_model")
    return dict(source)
```

Modify `temu_y2_women/public_source_adapter.py`:

```python
from temu_y2_women.public_source_adapters.whowhatwear_roundup import parse_whowhatwear_roundup_html


def resolve_public_source_adapter(adapter_id: str) -> Adapter:
    adapters = {
        "whowhatwear_editorial_v1": parse_whowhatwear_editorial_html,
        "marieclaire_editorial_v1": parse_marieclaire_editorial_html,
        "whowhatwear_roundup_v1": parse_whowhatwear_roundup_html,
    }
    ...
```

Create `temu_y2_women/public_source_adapters/whowhatwear_roundup.py`:

```python
from __future__ import annotations

from html.parser import HTMLParser
from typing import Any

from temu_y2_women.errors import GenerationError


class _RoundupCardParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.page_title = ""
        self.captured_at = ""
        self.cards: list[dict[str, str]] = []
        self._in_title = False
        self._in_card = False
        self._current: dict[str, str] | None = None
        self._capture_title = False
        self._capture_brand = False

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attr_map = {name: value or "" for name, value in attrs}
        if tag == "title":
            self._in_title = True
        if tag == "meta" and attr_map.get("property") == "article:published_time":
            self.captured_at = attr_map.get("content", "")[:10]
        if attr_map.get("data-card") == "":
            self._in_card = True
            self._current = {"title": "", "image_url": "", "source_url": "", "brand_text": ""}
        if self._in_card and tag == "a" and attr_map.get("data-card-link") == "":
            self._current["source_url"] = attr_map.get("href", "")
        if self._in_card and tag == "img":
            self._current["image_url"] = attr_map.get("src", "")
        if self._in_card and attr_map.get("data-card-title") == "":
            self._capture_title = True
        if self._in_card and attr_map.get("data-card-brand") == "":
            self._capture_brand = True

    def handle_endtag(self, tag: str) -> None:
        if tag == "title":
            self._in_title = False
        if tag == "li" and self._in_card and self._current is not None:
            self.cards.append(self._current)
            self._current = None
            self._in_card = False
        if tag in {"span", "a"}:
            self._capture_title = False
            self._capture_brand = False

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title:
            self.page_title = text
        if self._capture_title and self._current is not None:
            self._current["title"] = text
        if self._capture_brand and self._current is not None:
            self._current["brand_text"] = text


def parse_whowhatwear_roundup_html(source: dict[str, Any], html: str, fetched_at: str) -> dict[str, Any]:
    parser = _RoundupCardParser()
    parser.feed(html)
    if not parser.page_title:
        raise GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message="missing roundup page title", details={"field": "page_title"})
    if not parser.captured_at:
        raise GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message="missing roundup published date", details={"field": "captured_at"})
    if not parser.cards:
        raise GenerationError(code="INVALID_PUBLIC_SOURCE_HTML", message="missing roundup cards", details={"field": "cards"})
    cards = [
        {
            "card_id": f"{source['source_id']}-card-{index:03d}",
            "rank": index,
            "title": card["title"],
            "image_url": card["image_url"],
            "source_url": card["source_url"],
            "price_text": "",
            "brand_text": card["brand_text"],
            "badges": [],
        }
        for index, card in enumerate(parser.cards, start=1)
    ]
    return {
        "schema_version": "public-roundup-source-snapshot-v1",
        "source_id": source["source_id"],
        "source_type": source["source_type"],
        "source_url": source["source_url"],
        "captured_at": parser.captured_at,
        "fetched_at": fetched_at,
        "target_market": source["target_market"],
        "category": source["category"],
        "page_title": parser.page_title,
        "page_context_tags": ["summer", "shopping", "dress"],
        "cards": cards,
        "warnings": [],
    }
```

Add this roundup source record to `data/refresh/dress/source_registry.json`:

```json
{
  "source_id": "whowhatwear-best-summer-dresses-2025",
  "source_type": "public_roundup_web",
  "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
  "target_market": "US",
  "category": "dress",
  "fetch_mode": "html",
  "adapter_id": "whowhatwear_roundup_v1",
  "default_price_band": "mid",
  "pipeline_mode": "roundup_image_cards",
  "card_limit": 12,
  "aggregation_threshold": 2,
  "observation_model": "gpt-4.1-mini",
  "priority": 70,
  "weight": 0.7,
  "enabled": true
}
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```bash
python -m unittest tests.test_public_source_registry tests.test_public_source_adapter -v
```

Expected:
- `PASS`
- registry now loads the roundup source
- adapter now parses the roundup snapshot fixture

- [ ] **Step 5: Commit**

```bash
git add data/refresh/dress/source_registry.json temu_y2_women/public_source_registry.py temu_y2_women/public_source_adapter.py temu_y2_women/public_source_adapters/whowhatwear_roundup.py tests/test_public_source_registry.py tests/test_public_source_adapter.py tests/fixtures/public_sources/dress/whowhatwear-best-summer-dresses-2025.html tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json
git commit -m "feat(refresh): add roundup source routing and adapter"
```

### Task 2: Add deterministic card observations and roundup canonical aggregation

**Files:**
- Create: `temu_y2_women/public_card_observer.py`
- Create: `temu_y2_women/roundup_canonical_signal_builder.py`
- Create: `tests/test_public_card_observer.py`
- Create: `tests/test_roundup_canonical_signal_builder.py`
- Create: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-card-observations.json`
- Create: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`

- [ ] **Step 1: Write the failing observer and aggregation tests**

Create `tests/test_public_card_observer.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import unittest


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class PublicCardObserverTest(unittest.TestCase):
    def test_observe_roundup_cards_keeps_only_whitelisted_slots_and_records_abstentions(self) -> None:
        from temu_y2_women.public_card_observer import observe_roundup_cards

        snapshot = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json")

        def fake_observer(card: dict[str, object]) -> dict[str, object]:
            if card["card_id"] == "whowhatwear-best-summer-dresses-2025-card-001":
                return {
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                        {"slot": "color_family", "value": "white", "evidence_summary": "dress reads bright white"},
                        {"slot": "unsupported_slot", "value": "ignore", "evidence_summary": "bad"},
                    ],
                    "abstained_slots": ["waistline", "opacity_level"],
                    "warnings": [],
                }
            if card["card_id"] == "whowhatwear-best-summer-dresses-2025-card-002":
                return {
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                        {"slot": "pattern", "value": "polka dot", "evidence_summary": "repeating dotted print"},
                    ],
                    "abstained_slots": ["opacity_level"],
                    "warnings": [],
                }
            return {
                "observed_slots": [
                    {"slot": "waistline", "value": "drop waist", "evidence_summary": "seam sits below natural waist"},
                    {"slot": "dress_length", "value": "midi", "evidence_summary": "hemline lands mid-calf"},
                ],
                "abstained_slots": ["opacity_level"],
                "warnings": ["pattern not clearly visible"],
            }

        result = observe_roundup_cards(snapshot=snapshot, observation_model="fake-roundup-observer", observe_card=fake_observer, card_limit=2)

        expected = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-card-observations.json")
        self.assertEqual(result, expected)
```

Create `tests/test_roundup_canonical_signal_builder.py`:

```python
from __future__ import annotations

import json
from pathlib import Path
import unittest


_FIXTURE_DIR = Path("tests/fixtures/public_sources/dress")


class RoundupCanonicalSignalBuilderTest(unittest.TestCase):
    def test_build_roundup_canonical_signals_aggregates_repeated_slot_values(self) -> None:
        from temu_y2_women.roundup_canonical_signal_builder import build_roundup_canonical_signals

        snapshot = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json")
        observations = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-card-observations.json")

        result = build_roundup_canonical_signals(
            snapshot=snapshot,
            observations=observations,
            default_price_band="mid",
            aggregation_threshold=2,
        )

        expected = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json")
        self.assertEqual(result, expected)


def _read_json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))
```

Create `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-card-observations.json`:

```json
{
  "schema_version": "public-card-observations-v1",
  "source_id": "whowhatwear-best-summer-dresses-2025",
  "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
  "fetched_at": "2026-04-28T00:00:00Z",
  "observation_model": "fake-roundup-observer",
  "card_limit": 2,
  "cards": [
    {
      "card_id": "whowhatwear-best-summer-dresses-2025-card-001",
      "rank": 1,
      "title": "White Mini Dress",
      "image_url": "https://images.example.com/white-mini-dress.jpg",
      "source_url": "https://shop.example.com/products/white-mini-dress",
      "observed_slots": [
        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
        {"slot": "color_family", "value": "white", "evidence_summary": "dress reads bright white"}
      ],
      "abstained_slots": ["waistline", "opacity_level"],
      "warnings": []
    },
    {
      "card_id": "whowhatwear-best-summer-dresses-2025-card-002",
      "rank": 2,
      "title": "Polka-Dot Mini Dress",
      "image_url": "https://images.example.com/polka-dot-mini-dress.jpg",
      "source_url": "https://shop.example.com/products/polka-dot-mini-dress",
      "observed_slots": [
        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
        {"slot": "pattern", "value": "polka dot", "evidence_summary": "repeating dotted print"}
      ],
      "abstained_slots": ["opacity_level"],
      "warnings": []
    }
  ]
}
```

Create `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`:

```json
{
  "schema_version": "canonical-signals-v1",
  "signals": [
    {
      "canonical_signal_id": "whowhatwear-best-summer-dresses-2025-dress_length-mini-001",
      "source_id": "whowhatwear-best-summer-dresses-2025",
      "source_type": "public_roundup_web",
      "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
      "captured_at": "2025-06-20",
      "fetched_at": "2026-04-28T00:00:00Z",
      "target_market": "US",
      "category": "dress",
      "title": "Best Summer Dresses 2025",
      "summary": "Observed dress_length=mini across 2 roundup cards.",
      "evidence_excerpt": "White Mini Dress | Polka-Dot Mini Dress",
      "observed_occasion_tags": [],
      "observed_season_tags": ["summer"],
      "manual_tags": ["summer", "shopping", "dress"],
      "observed_price_band": "mid",
      "price_band_resolution": "source_default",
      "status": "active",
      "extraction_provenance": {
        "aggregation_kind": "roundup_card_slot_aggregation",
        "slot": "dress_length",
        "value": "mini",
        "supporting_card_ids": [
          "whowhatwear-best-summer-dresses-2025-card-001",
          "whowhatwear-best-summer-dresses-2025-card-002"
        ],
        "supporting_card_count": 2,
        "card_limit": 2,
        "aggregation_threshold": 2,
        "adapter_version": "whowhatwear_roundup_v1",
        "observation_model": "fake-roundup-observer",
        "warnings": []
      }
    }
  ]
}
```

- [ ] **Step 2: Run the targeted tests to verify they fail**

Run:

```bash
python -m unittest tests.test_public_card_observer tests.test_roundup_canonical_signal_builder -v
```

Expected:
- `FAIL` with `ModuleNotFoundError` for the new modules

- [ ] **Step 3: Implement observation contract and roundup aggregation**

Create `temu_y2_women/public_card_observer.py`:

```python
from __future__ import annotations

from typing import Any, Callable

from temu_y2_women.errors import GenerationError


CardObserver = Callable[[dict[str, Any]], dict[str, Any]]
_ALLOWED_SLOTS = {
    "silhouette",
    "neckline",
    "sleeve",
    "dress_length",
    "pattern",
    "color_family",
    "waistline",
    "print_scale",
    "opacity_level",
    "detail",
}


def observe_roundup_cards(
    snapshot: dict[str, Any],
    observation_model: str,
    observe_card: CardObserver,
    card_limit: int,
) -> dict[str, Any]:
    cards = list(snapshot["cards"])[:card_limit]
    observed_cards = [_observe_single_card(card, observe_card) for card in cards]
    return {
        "schema_version": "public-card-observations-v1",
        "source_id": snapshot["source_id"],
        "source_url": snapshot["source_url"],
        "fetched_at": snapshot["fetched_at"],
        "observation_model": observation_model,
        "card_limit": card_limit,
        "cards": observed_cards,
    }


def _observe_single_card(card: dict[str, Any], observe_card: CardObserver) -> dict[str, Any]:
    payload = observe_card(card)
    observed_slots = []
    for item in payload.get("observed_slots", []):
        slot = str(item["slot"])
        if slot not in _ALLOWED_SLOTS:
            continue
        observed_slots.append(
            {
                "slot": slot,
                "value": str(item["value"]),
                "evidence_summary": str(item["evidence_summary"]),
            }
        )
    abstained_slots = [str(slot) for slot in payload.get("abstained_slots", []) if str(slot) in _ALLOWED_SLOTS]
    if not observed_slots and not abstained_slots:
        raise GenerationError(code="INVALID_PUBLIC_CARD_OBSERVATION", message="observer returned no usable slots", details={"card_id": card["card_id"]})
    return {
        "card_id": card["card_id"],
        "rank": card["rank"],
        "title": card["title"],
        "image_url": card["image_url"],
        "source_url": card["source_url"],
        "observed_slots": observed_slots,
        "abstained_slots": abstained_slots,
        "warnings": [str(item) for item in payload.get("warnings", [])],
    }
```

Create `temu_y2_women/roundup_canonical_signal_builder.py`:

```python
from __future__ import annotations

from collections import defaultdict
from typing import Any


def build_roundup_canonical_signals(
    snapshot: dict[str, Any],
    observations: dict[str, Any],
    default_price_band: str,
    aggregation_threshold: int,
) -> dict[str, Any]:
    grouped: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for card in observations["cards"]:
        for slot in card["observed_slots"]:
            grouped[(slot["slot"], slot["value"])].append(card)
    signals = []
    for index, ((slot, value), cards) in enumerate(sorted(grouped.items()), start=1):
        if len(cards) < aggregation_threshold:
            continue
        signals.append(
            {
                "canonical_signal_id": f"{snapshot['source_id']}-{slot}-{value.replace(' ', '-')}-{index:03d}",
                "source_id": snapshot["source_id"],
                "source_type": snapshot["source_type"],
                "source_url": snapshot["source_url"],
                "captured_at": snapshot["captured_at"],
                "fetched_at": snapshot["fetched_at"],
                "target_market": snapshot["target_market"],
                "category": snapshot["category"],
                "title": snapshot["page_title"],
                "summary": f"Observed {slot}={value} across {len(cards)} roundup cards.",
                "evidence_excerpt": " | ".join(card["title"] for card in cards[:3]),
                "observed_occasion_tags": [],
                "observed_season_tags": ["summer"],
                "manual_tags": list(snapshot["page_context_tags"]),
                "observed_price_band": default_price_band,
                "price_band_resolution": "source_default",
                "status": "active",
                "extraction_provenance": {
                    "aggregation_kind": "roundup_card_slot_aggregation",
                    "slot": slot,
                    "value": value,
                    "supporting_card_ids": [card["card_id"] for card in cards],
                    "supporting_card_count": len(cards),
                    "card_limit": observations["card_limit"],
                    "aggregation_threshold": aggregation_threshold,
                    "adapter_version": "whowhatwear_roundup_v1",
                    "observation_model": observations["observation_model"],
                    "warnings": [],
                },
            }
        )
    return {"schema_version": "canonical-signals-v1", "signals": signals}
```

- [ ] **Step 4: Run the targeted tests to verify they pass**

Run:

```bash
python -m unittest tests.test_public_card_observer tests.test_roundup_canonical_signal_builder -v
```

Expected:
- `PASS`
- non-whitelisted slots are dropped
- repeated `dress_length=mini` becomes a single canonical signal with `supporting_card_ids`

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/public_card_observer.py temu_y2_women/roundup_canonical_signal_builder.py tests/test_public_card_observer.py tests/test_roundup_canonical_signal_builder.py tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-card-observations.json tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json
git commit -m "feat(refresh): add roundup card observation aggregation"
```

### Task 3: Add the live OpenAI-compatible card observer without coupling tests to the network

**Files:**
- Create: `temu_y2_women/public_card_observer_openai.py`
- Create: `tests/test_public_card_observer_openai.py`

- [ ] **Step 1: Write the failing live observer tests**

Create `tests/test_public_card_observer_openai.py`:

```python
from __future__ import annotations

import json
import unittest
from unittest.mock import MagicMock, patch


class PublicCardObserverOpenAITest(unittest.TestCase):
    def test_build_openai_public_card_observer_requires_api_key(self) -> None:
        from temu_y2_women.public_card_observer_openai import build_openai_public_card_observer

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaisesRegex(Exception, "api_key"):
                build_openai_public_card_observer(model="gpt-4.1-mini")

    def test_observe_card_parses_json_payload(self) -> None:
        from temu_y2_women.public_card_observer_openai import build_openai_public_card_observer

        fake_client = MagicMock()
        fake_response = MagicMock()
        fake_response.output_text = json.dumps(
            {
                "observed_slots": [
                    {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline appears above the knee"},
                    {"slot": "color_family", "value": "white", "evidence_summary": "fabric reads bright white"}
                ],
                "abstained_slots": ["waistline", "opacity_level"],
                "warnings": []
            }
        )
        fake_client.responses.create.return_value = fake_response

        with patch("temu_y2_women.public_card_observer_openai.OpenAI", return_value=fake_client):
            observer = build_openai_public_card_observer(
                api_key="test-key",
                base_url="https://example.com/v1",
                model="gpt-4.1-mini",
            )
            result = observer.observe_card(
                {
                    "card_id": "card-001",
                    "title": "White Mini Dress",
                    "image_url": "https://images.example.com/white-mini-dress.jpg",
                    "source_url": "https://shop.example.com/products/white-mini-dress",
                }
            )

        self.assertEqual(result["observed_slots"][0]["slot"], "dress_length")
        self.assertEqual(result["abstained_slots"], ["waistline", "opacity_level"])
        fake_client.responses.create.assert_called_once()
```

- [ ] **Step 2: Run the targeted test to verify it fails**

Run:

```bash
python -m unittest tests.test_public_card_observer_openai -v
```

Expected:
- `FAIL` with `ModuleNotFoundError` for `public_card_observer_openai`

- [ ] **Step 3: Implement the live observer wrapper**

Create `temu_y2_women/public_card_observer_openai.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from typing import Any

from openai import OpenAI

from temu_y2_women.errors import GenerationError


@dataclass(frozen=True, slots=True)
class OpenAIPublicCardObserverConfig:
    api_key: str
    base_url: str
    model: str


class OpenAIPublicCardObserver:
    def __init__(self, config: OpenAIPublicCardObserverConfig) -> None:
        self._config = config
        self._client = OpenAI(api_key=config.api_key, base_url=config.base_url)

    def observe_card(self, card: dict[str, Any]) -> dict[str, Any]:
        response = self._client.responses.create(
            model=self._config.model,
            input=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": (
                                "Observe this dress product image. Return JSON with keys observed_slots, abstained_slots, warnings. "
                                "Only use slots silhouette, neckline, sleeve, dress_length, pattern, color_family, waistline, "
                                "print_scale, opacity_level, detail. If a slot is not clearly visible, abstain."
                            ),
                        },
                        {"type": "input_image", "image_url": card["image_url"]},
                    ],
                }
            ],
        )
        try:
            payload = json.loads(response.output_text)
        except json.JSONDecodeError as error:
            raise GenerationError(code="INVALID_PUBLIC_CARD_OBSERVATION", message="observer returned invalid JSON", details={"card_id": card["card_id"]}) from error
        return payload


def build_openai_public_card_observer(
    api_key: str | None = None,
    base_url: str | None = None,
    model: str = "gpt-4.1-mini",
) -> OpenAIPublicCardObserver:
    resolved_api_key = (api_key or os.getenv("OPENAI_COMPAT_EXPANSION_API_KEY", "")).strip()
    resolved_base_url = (base_url or os.getenv("OPENAI_COMPAT_BASE_URL", "")).strip()
    if not resolved_api_key:
        raise GenerationError(code="INVALID_PUBLIC_CARD_OBSERVER_CONFIG", message="public card observer requires api key", details={"field": "api_key"})
    if not resolved_base_url:
        raise GenerationError(code="INVALID_PUBLIC_CARD_OBSERVER_CONFIG", message="public card observer requires base_url", details={"field": "base_url"})
    return OpenAIPublicCardObserver(
        OpenAIPublicCardObserverConfig(api_key=resolved_api_key, base_url=resolved_base_url, model=model)
    )
```

Implementation note for this task:

- The live card observer is an **analysis** path that reads a card image and returns structured slot observations.
- Do **not** switch this task to `gpt-image-2` edit/generation endpoints.
- If later work in this repository touches reference-image rendering, the rule stays:
  1. `/v1/images/edits`
  2. if edits fail or are unavailable, stop and surface the error directly

- [ ] **Step 4: Run the targeted test to verify it passes**

Run:

```bash
python -m unittest tests.test_public_card_observer_openai -v
```

Expected:
- `PASS`
- no network call escapes the test

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/public_card_observer_openai.py tests/test_public_card_observer_openai.py
git commit -m "feat(refresh): add live public card observer wrapper"
```

### Task 4: Integrate roundup image cards into `public_signal_refresh`

**Files:**
- Modify: `temu_y2_women/public_signal_refresh.py`
- Modify: `tests/test_public_signal_refresh.py`
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`

- [ ] **Step 1: Write the failing mixed-source refresh test**

Append this test to `tests/test_public_signal_refresh.py`:

```python
    def test_run_public_signal_refresh_merges_editorial_and_roundup_sources(self) -> None:
        from temu_y2_women.public_signal_refresh import run_public_signal_refresh

        def fake_card_observer(card: dict[str, object]) -> dict[str, object]:
            if card["card_id"].endswith("001"):
                return {
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                        {"slot": "color_family", "value": "white", "evidence_summary": "dress reads bright white"},
                    ],
                    "abstained_slots": ["waistline", "opacity_level"],
                    "warnings": [],
                }
            if card["card_id"].endswith("002"):
                return {
                    "observed_slots": [
                        {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
                        {"slot": "pattern", "value": "polka dot", "evidence_summary": "repeating dotted print"},
                    ],
                    "abstained_slots": ["opacity_level"],
                    "warnings": [],
                }
            return {
                "observed_slots": [
                    {"slot": "waistline", "value": "drop waist", "evidence_summary": "seam sits below natural waist"}
                ],
                "abstained_slots": ["opacity_level"],
                "warnings": [],
            }

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            registry_path = temp_root / "registry.json"
            registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")
            result = run_public_signal_refresh(
                registry_path=registry_path,
                output_root=temp_root,
                fetched_at="2026-04-28T00:00:00Z",
                fetcher=_mixed_registry_fetcher(),
                card_image_observer=fake_card_observer,
            )
            run_dir = temp_root / result["run_id"]
            card_observations = _read_json(run_dir / "card_observations" / "whowhatwear-best-summer-dresses-2025.json")

        self.assertEqual(card_observations["schema_version"], "public-card-observations-v1")
        self.assertEqual(result["source_summary"], {"total": 2, "succeeded": 2, "failed": 0})
        roundup_detail = next(item for item in result["source_details"] if item["source_id"] == "whowhatwear-best-summer-dresses-2025")
        self.assertEqual(roundup_detail["card_count_extracted"], 3)
        self.assertEqual(roundup_detail["card_count_observed"], 3)
        self.assertEqual(roundup_detail["aggregated_signal_count"], 1)
        self.assertEqual(roundup_detail["card_limit"], 12)
        self.assertEqual(roundup_detail["aggregation_threshold"], 2)
```

Add these helpers to the same file:

```python
def _mixed_source_registry() -> dict[str, object]:
    return {
        "schema_version": "public-source-registry-v1",
        "sources": [
            _single_source_registry()["sources"][0],
            {
                "source_id": "whowhatwear-best-summer-dresses-2025",
                "source_type": "public_roundup_web",
                "source_url": "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025",
                "target_market": "US",
                "category": "dress",
                "fetch_mode": "html",
                "adapter_id": "whowhatwear_roundup_v1",
                "default_price_band": "mid",
                "pipeline_mode": "roundup_image_cards",
                "card_limit": 12,
                "aggregation_threshold": 2,
                "observation_model": "gpt-4.1-mini",
                "priority": 70,
                "weight": 0.7,
                "enabled": True,
            },
        ],
    }


def _mixed_registry_fetcher() -> Callable[[str], str]:
    html_by_url = {
        "https://www.whowhatwear.com/fashion/summer/summer-2025-dress-trends": _fixture_html(),
        "https://www.whowhatwear.com/fashion/shopping/best-summer-dresses-2025": (
            _SOURCE_FIXTURE_DIR / "whowhatwear-best-summer-dresses-2025.html"
        ).read_text(encoding="utf-8"),
    }

    def fetcher(url: str) -> str:
        return html_by_url[url]

    return fetcher
```

- [ ] **Step 2: Run the targeted refresh test to verify it fails**

Run:

```bash
python -m unittest tests.test_public_signal_refresh.PublicSignalRefreshTest.test_run_public_signal_refresh_merges_editorial_and_roundup_sources -v
```

Expected:
- `FAIL` because `run_public_signal_refresh()` does not yet accept `card_image_observer`

- [ ] **Step 3: Implement source-mode routing, card observation artifacts, and mixed canonical merge**

Modify `temu_y2_women/public_signal_refresh.py` to route by `pipeline_mode`:

```python
from temu_y2_women.public_card_observer import observe_roundup_cards
from temu_y2_women.public_card_observer_openai import build_openai_public_card_observer
from temu_y2_women.roundup_canonical_signal_builder import build_roundup_canonical_signals


def run_public_signal_refresh(
    registry_path: Path,
    output_root: Path,
    fetched_at: str,
    fetcher: Fetcher | None = None,
    source_ids: list[str] | None = None,
    card_image_observer: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    ...
```

Add roundup-aware canonical collection:

```python
def _build_canonical_payload(
    raw_snapshots: list[dict[str, Any]],
    selected_sources: list[dict[str, Any]],
    errors: list[dict[str, Any]],
    card_image_observer: Callable[[dict[str, Any]], dict[str, Any]] | None,
) -> tuple[dict[str, Any], dict[str, dict[str, Any]], list[dict[str, Any]]]:
    signals: list[dict[str, Any]] = []
    observations_by_source: dict[str, dict[str, Any]] = {}
    source_defaults = {source["source_id"]: source["default_price_band"] for source in selected_sources}
    source_lookup = {source["source_id"]: source for source in selected_sources}
    for snapshot in raw_snapshots:
        source_id = str(snapshot["source_id"])
        source = source_lookup[source_id]
        try:
            if source["pipeline_mode"] == "roundup_image_cards":
                observer = card_image_observer or build_openai_public_card_observer(model=str(source["observation_model"])).observe_card
                observations = observe_roundup_cards(
                    snapshot=snapshot,
                    observation_model=str(source["observation_model"]),
                    observe_card=observer,
                    card_limit=int(source["card_limit"]),
                )
                observations_by_source[source_id] = observations
                payload = build_roundup_canonical_signals(
                    snapshot=snapshot,
                    observations=observations,
                    default_price_band=source_defaults[source_id],
                    aggregation_threshold=int(source["aggregation_threshold"]),
                )
            else:
                payload = build_canonical_signals(snapshot, source_defaults[source_id])
            signals.extend(list(payload["signals"]))
        except Exception as error:
            errors.append(_source_error(source_id, "canonicalize", error, "PUBLIC_SOURCE_CANONICALIZE_FAILED"))
    return {"schema_version": _CANONICAL_SCHEMA_VERSION, "signals": signals}, observations_by_source, errors
```

Write observation artifacts and report details:

```python
def _write_refresh_outputs(
    run_dir: Path,
    registry_snapshot: dict[str, Any],
    raw_snapshots: list[dict[str, Any]],
    canonical_payload: dict[str, Any],
    report: dict[str, Any],
    observations_by_source: dict[str, dict[str, Any]],
) -> None:
    _write_json(run_dir / "source_registry_snapshot.json", registry_snapshot)
    _write_raw_snapshots(run_dir / "raw_sources", raw_snapshots)
    _write_observations(run_dir / "card_observations", observations_by_source)
    _write_json(run_dir / "canonical_signals.json", canonical_payload)
    _write_json(run_dir / "refresh_report.json", report)


def _write_observations(path: Path, observations_by_source: dict[str, dict[str, Any]]) -> None:
    path.mkdir(parents=True, exist_ok=True)
    for source_id, payload in observations_by_source.items():
        _write_json(path / f"{source_id}.json", payload)
```

Extend source detail payload for roundup sources:

```python
        "card_count_extracted": len(snapshot_lookup.get(source_id, {}).get("cards", [])),
        "card_count_observed": len(observations_lookup.get(source_id, {}).get("cards", [])),
        "aggregated_signal_count": len(signals),
        "card_limit": source.get("card_limit", 0),
        "aggregation_threshold": source.get("aggregation_threshold", 0),
```

- [ ] **Step 4: Run the targeted refresh test to verify it passes**

Run:

```bash
python -m unittest tests.test_public_signal_refresh.PublicSignalRefreshTest.test_run_public_signal_refresh_merges_editorial_and_roundup_sources -v
```

Expected:
- `PASS`
- refresh run writes `card_observations/<source_id>.json`
- roundup source detail reports card counts and aggregated signal count

- [ ] **Step 5: Commit**

```bash
git add temu_y2_women/public_signal_refresh.py tests/test_public_signal_refresh.py tests/fixtures/public_refresh/dress/expected-refresh-report.json
git commit -m "feat(refresh): integrate roundup image observation flow"
```

### Task 5: Run final regression and verify the diff stays within roundup-refresh scope

**Files:**
- No new files expected unless regression exposes a concrete defect in Tasks 1-4.

- [ ] **Step 1: Run the refresh-related regression suite**

Run:

```bash
python -m unittest tests.test_public_source_registry tests.test_public_source_adapter tests.test_public_card_observer tests.test_public_card_observer_openai tests.test_roundup_canonical_signal_builder tests.test_canonical_signal_builder tests.test_public_signal_refresh tests.test_signal_ingestion -v
```

Expected:
- all listed tests pass

- [ ] **Step 2: Run Python compilation checks**

Run:

```bash
python -m py_compile temu_y2_women/public_source_registry.py temu_y2_women/public_source_adapter.py temu_y2_women/public_source_adapters/whowhatwear_roundup.py temu_y2_women/public_card_observer.py temu_y2_women/public_card_observer_openai.py temu_y2_women/roundup_canonical_signal_builder.py temu_y2_women/public_signal_refresh.py tests/test_public_source_registry.py tests/test_public_source_adapter.py tests/test_public_card_observer.py tests/test_public_card_observer_openai.py tests/test_roundup_canonical_signal_builder.py tests/test_public_signal_refresh.py
```

Expected:
- no output

- [ ] **Step 3: Run the function-length guardrail**

Run:

```bash
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- `OK`

- [ ] **Step 4: Inspect final git scope**

Run:

```bash
git status --short
git diff --stat
git log --oneline --decorate -5
```

Expected:
- diff is limited to roundup source config, adapter, observer, canonical builder, refresh wiring, and related tests/fixtures
