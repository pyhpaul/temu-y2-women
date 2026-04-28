# Image Structured Signal Ingestion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让公开商品卡图观察结果以结构化候选的形式直接进入 `signal_ingestion`，支持新 `value` 进入 `draft_elements`，同时保持现有文本 refresh / ingestion 主链兼容。

**Architecture:** 先在 `roundup_canonical_signal_builder.py` 上为页面级聚合 signal 补 `structured_candidates`，再由 `public_signal_refresh.py` 透传到 `signal_bundle.json`。随后升级 `signal_ingestion.py` 的输入校验、normalization、候选抽取和 provenance 逻辑，使其支持文本规则与结构化图片候选双通道聚合，最后用 mixed-source refresh 集成测试验证“新 value 仅靠图片链路入 draft”的闭环。

**Tech Stack:** Python 3、现有 `unittest` 测试体系、JSON fixtures、`temu_y2_women` 现有 refresh / ingestion 模块、`validate_python_function_length.py`、`validate_forbidden_patterns.py`。

---

## File Map

- Modify: `temu_y2_women/roundup_canonical_signal_builder.py`
- Modify: `temu_y2_women/public_signal_refresh.py`
- Modify: `temu_y2_women/signal_ingestion.py`
- Modify: `tests/test_roundup_canonical_signal_builder.py`
- Modify: `tests/test_public_signal_refresh.py`
- Modify: `tests/test_signal_ingestion.py`
- Modify: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-ingestion-report.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`

## Task 1: 为 roundup canonical signals 增加 `structured_candidates`

**Files:**
- Modify: `temu_y2_women/roundup_canonical_signal_builder.py`
- Modify: `tests/test_roundup_canonical_signal_builder.py`
- Modify: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`

- [ ] **Step 1: 先写 builder 失败测试，明确 `structured_candidates` contract**

```python
def test_build_roundup_canonical_signals_attaches_structured_candidates(self) -> None:
    from temu_y2_women.roundup_canonical_signal_builder import build_roundup_canonical_signals

    snapshot = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-raw-source-snapshot.json")
    observations = _read_json(_FIXTURE_DIR / "expected-whowhatwear-best-summer-dresses-2025-card-observations.json")

    result = build_roundup_canonical_signals(
        snapshot=snapshot,
        observations=observations,
        default_price_band="mid",
        aggregation_threshold=2,
    )

    signal = result["signals"][0]
    self.assertIn("structured_candidates", signal)
    self.assertEqual(len(signal["structured_candidates"]), 1)
    self.assertEqual(
        signal["structured_candidates"][0],
        {
            "slot": "dress_length",
            "value": "mini",
            "candidate_source": "roundup_card_image_aggregation",
            "supporting_card_ids": [
                "whowhatwear-best-summer-dresses-2025-card-001",
                "whowhatwear-best-summer-dresses-2025-card-002",
            ],
            "supporting_card_count": 2,
            "aggregation_threshold": 2,
            "observation_model": "fake-roundup-observer",
            "evidence_summary": "Observed dress_length=mini across 2 roundup cards.",
        },
    )
```

- [ ] **Step 2: 运行聚焦 builder 测试，确认当前失败**

Run: `python -m unittest tests.test_roundup_canonical_signal_builder.RoundupCanonicalSignalBuilderTest.test_build_roundup_canonical_signals_attaches_structured_candidates -v`

Expected:
- `FAIL`
- `structured_candidates` 还不存在

- [ ] **Step 3: 在 builder 中补结构化候选输出**

在 `temu_y2_women/roundup_canonical_signal_builder.py` 中，为 `_build_signal(...)` 增加 `structured_candidates`，并新增两个 helper，保持单函数不超过 60 行：

```python
def _structured_candidates(
    slot: str,
    value: str,
    cards: list[dict[str, Any]],
    observations: dict[str, Any],
    aggregation_threshold: int,
) -> list[dict[str, Any]]:
    return [
        {
            "slot": slot,
            "value": value,
            "candidate_source": "roundup_card_image_aggregation",
            "supporting_card_ids": [card["card_id"] for card in cards],
            "supporting_card_count": len(cards),
            "aggregation_threshold": aggregation_threshold,
            "observation_model": observations["observation_model"],
            "evidence_summary": f"Observed {slot}={value} across {len(cards)} roundup cards.",
        }
    ]


def _build_signal(...) -> dict[str, Any]:
    return {
        "canonical_signal_id": _canonical_signal_id(snapshot["source_id"], slot, value, index),
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
        "observed_season_tags": _observed_season_tags(snapshot),
        "manual_tags": list(snapshot["page_context_tags"]),
        "observed_price_band": default_price_band,
        "price_band_resolution": "source_default",
        "status": "active",
        "structured_candidates": _structured_candidates(slot, value, cards, observations, aggregation_threshold),
        "extraction_provenance": _provenance(observations, aggregation_threshold, slot, value, cards),
    }
```

同时更新 fixture `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`，给唯一 signal 增加对应 `structured_candidates` 数组。

- [ ] **Step 4: 重新运行 builder 测试，确认通过**

Run: `python -m unittest tests.test_roundup_canonical_signal_builder -v`

Expected:
- `PASS`
- 现有聚合断言继续通过
- 新增 `structured_candidates` 断言通过

- [ ] **Step 5: 提交 builder contract 改动**

```bash
git add \
  temu_y2_women/roundup_canonical_signal_builder.py \
  tests/test_roundup_canonical_signal_builder.py \
  tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json
git commit -m "feat: add structured candidates to roundup signals"
```

## Task 2: 让 refresh 透传 `structured_candidates` 到 signal bundle 与 report

**Files:**
- Modify: `temu_y2_women/public_signal_refresh.py`
- Modify: `tests/test_public_signal_refresh.py`

- [ ] **Step 1: 先写 refresh 失败测试，证明 bundle 会保留结构化候选**

```python
def test_run_public_signal_refresh_copies_structured_candidates_to_signal_bundle(self) -> None:
    from tempfile import TemporaryDirectory
    from temu_y2_women.public_signal_refresh import run_public_signal_refresh

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        registry_path = temp_root / "registry.json"
        registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")

        result = run_public_signal_refresh(
            registry_path=registry_path,
            output_root=temp_root / "runs",
            fetched_at="2026-04-29T00:00:00Z",
            fetcher=_mixed_registry_fetcher(),
            card_image_observer=_fake_card_observer,
        )

        run_dir = temp_root / "runs" / result["run_id"]
        bundle = _read_json(run_dir / "signal_bundle.json")
        roundup_signal = next(
            signal for signal in bundle["signals"] if signal["source_type"] == "public_roundup_web"
        )

    self.assertIn("structured_candidates", roundup_signal)
    self.assertEqual(roundup_signal["structured_candidates"][0]["candidate_source"], "roundup_card_image_aggregation")
```

- [ ] **Step 2: 运行聚焦 refresh 测试，确认当前失败**

Run: `python -m unittest tests.test_public_signal_refresh.PublicSignalRefreshTest.test_run_public_signal_refresh_copies_structured_candidates_to_signal_bundle -v`

Expected:
- `FAIL`
- `signal_bundle.json` 里的 roundup signal 当前不包含 `structured_candidates`

- [ ] **Step 3: 在 refresh 层透传候选，并补最小 report 统计**

在 `temu_y2_women/public_signal_refresh.py` 中新增两个 helper，并在 `_signal_bundle_record(...)` 中使用它们：

```python
def _optional_structured_candidates(signal: dict[str, Any]) -> list[dict[str, Any]] | None:
    candidates = signal.get("structured_candidates")
    if not isinstance(candidates, list) or not candidates:
        return None
    return [_signal_bundle_structured_candidate(item) for item in candidates]


def _signal_bundle_structured_candidate(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "slot": item["slot"],
        "value": item["value"],
        "candidate_source": item["candidate_source"],
        "supporting_card_ids": list(item["supporting_card_ids"]),
        "supporting_card_count": item["supporting_card_count"],
        "aggregation_threshold": item["aggregation_threshold"],
        "observation_model": item["observation_model"],
        "evidence_summary": item["evidence_summary"],
    }


def _signal_bundle_record(signal: dict[str, Any]) -> dict[str, Any]:
    record = {
        "signal_id": signal["canonical_signal_id"],
        "source_type": signal["source_type"],
        "source_url": signal["source_url"],
        "captured_at": signal["captured_at"],
        "target_market": signal["target_market"],
        "category": signal["category"],
        "title": signal["title"],
        "summary": signal["summary"],
        "observed_price_band": signal["observed_price_band"],
        "observed_occasion_tags": _filtered_signal_tags(signal, "observed_occasion_tags", "allowed_occasions"),
        "observed_season_tags": _filtered_signal_tags(signal, "observed_season_tags", "allowed_seasons"),
        "manual_tags": _filtered_signal_tags(signal, "manual_tags", "allowed_tags"),
        "status": signal["status"],
        "extraction_provenance": dict(signal["extraction_provenance"]),
    }
    structured_candidates = _optional_structured_candidates(signal)
    if structured_candidates is not None:
        record["structured_candidates"] = structured_candidates
    return record
```

如果刷新报告需要额外可读性，给 `roundup` source detail 增加：

```python
"structured_candidate_count": sum(
    len(signal.get("structured_candidates", [])) for signal in canonical_signals
),
```

- [ ] **Step 4: 运行 refresh 聚焦测试，确认通过**

Run: `python -m unittest tests.test_public_signal_refresh -v`

Expected:
- `PASS`
- 现有 mixed-source refresh 断言继续通过
- 新增 bundle 透传断言通过

- [ ] **Step 5: 提交 refresh 透传改动**

```bash
git add \
  temu_y2_women/public_signal_refresh.py \
  tests/test_public_signal_refresh.py
git commit -m "feat: pass structured candidates through refresh bundle"
```

## Task 3: 为 ingestion 增加结构化候选校验与 normalization

**Files:**
- Modify: `temu_y2_women/signal_ingestion.py`
- Modify: `tests/test_signal_ingestion.py`

- [ ] **Step 1: 先写两个 ingestion 失败测试：接受合法 structured candidates、拒绝非法 structured candidates**

```python
def test_ingest_dress_signals_accepts_structured_candidates(self) -> None:
    from temu_y2_women.signal_ingestion import ingest_dress_signals

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / "signals.json"
        input_path.write_text(
            json.dumps(
                {
                    "schema_version": "signal-bundle-v1",
                    "signals": [
                        {
                            "signal_id": "dress-image-001",
                            "source_type": "public_roundup_web",
                            "source_url": "https://example.com/roundup",
                            "captured_at": "2026-04-29",
                            "target_market": "US",
                            "category": "dress",
                            "title": "Observed roundup",
                            "summary": "Observed neckline trend from public cards.",
                            "observed_price_band": "mid",
                            "observed_occasion_tags": ["vacation"],
                            "observed_season_tags": ["summer"],
                            "manual_tags": ["summer", "dress"],
                            "status": "active",
                            "structured_candidates": [
                                {
                                    "slot": "neckline",
                                    "value": "scoop neckline",
                                    "candidate_source": "roundup_card_image_aggregation",
                                    "supporting_card_ids": ["card-001", "card-002"],
                                    "supporting_card_count": 2,
                                    "aggregation_threshold": 2,
                                    "observation_model": "fake-roundup-observer",
                                    "evidence_summary": "Observed neckline=scoop neckline across 2 roundup cards.",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        report = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

    self.assertEqual(report["error"]["code"] if "error" in report else None, None)


def test_ingest_dress_signals_rejects_invalid_structured_candidates(self) -> None:
    from temu_y2_women.signal_ingestion import ingest_dress_signals

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / "signals.json"
        input_path.write_text(
            json.dumps(
                {
                    "schema_version": "signal-bundle-v1",
                    "signals": [
                        {
                            "signal_id": "dress-image-002",
                            "source_type": "public_roundup_web",
                            "source_url": "https://example.com/roundup",
                            "captured_at": "2026-04-29",
                            "target_market": "US",
                            "category": "dress",
                            "title": "Observed roundup",
                            "summary": "Observed invalid structured candidate.",
                            "observed_price_band": "mid",
                            "observed_occasion_tags": [],
                            "observed_season_tags": ["summer"],
                            "manual_tags": ["summer", "dress"],
                            "status": "active",
                            "structured_candidates": [
                                {
                                    "slot": "unknown_slot",
                                    "value": "",
                                    "candidate_source": "roundup_card_image_aggregation",
                                    "supporting_card_ids": [],
                                    "supporting_card_count": 0,
                                    "aggregation_threshold": 2,
                                    "observation_model": "fake-roundup-observer",
                                    "evidence_summary": "bad candidate",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        result = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

    self.assertEqual(result["error"]["code"], "INVALID_SIGNAL_INPUT")
```

- [ ] **Step 2: 运行这两个聚焦测试，确认当前行为未覆盖**

Run: `python -m unittest tests.test_signal_ingestion.SignalIngestionTest.test_ingest_dress_signals_accepts_structured_candidates tests.test_signal_ingestion.SignalIngestionTest.test_ingest_dress_signals_rejects_invalid_structured_candidates -v`

Expected:
- 第一个测试 `FAIL`，因为 structured candidates 还未被消费
- 第二个测试 `FAIL` 或报错位置不正确，说明校验路径尚未建立

- [ ] **Step 3: 在 ingestion 中建立结构化候选校验与 normalization**

在 `temu_y2_women/signal_ingestion.py` 中新增一个 required-field 集和四个 helper：

```python
_STRUCTURED_CANDIDATE_REQUIRED_FIELDS = {
    "slot",
    "value",
    "candidate_source",
    "supporting_card_ids",
    "supporting_card_count",
    "aggregation_threshold",
    "observation_model",
    "evidence_summary",
}


def _validate_structured_candidates(path: Path, index: int, signal: dict[str, Any], taxonomy: dict[str, Any]) -> None:
    candidates = signal.get("structured_candidates")
    if candidates is None:
        return
    if not isinstance(candidates, list):
        raise _signal_error(path, index, "structured_candidates", candidates, "signal field 'structured_candidates' must be a list")
    for candidate in candidates:
        _validate_structured_candidate(path, index, candidate, taxonomy)


def _validate_structured_candidate(path: Path, index: int, candidate: Any, taxonomy: dict[str, Any]) -> None:
    if not isinstance(candidate, dict):
        raise _signal_error(path, index, "structured_candidates", candidate, "structured candidate must be an object")
    missing = sorted(_STRUCTURED_CANDIDATE_REQUIRED_FIELDS.difference(candidate.keys()))
    if missing:
        raise _signal_error(path, index, "structured_candidates", missing[0], "structured candidate is missing required fields")
    slot = _canonical_string(str(candidate["slot"]))
    value = " ".join(str(candidate["value"]).split()).strip().casefold()
    if slot not in taxonomy["allowed_slots"] or not value:
        raise _signal_error(path, index, "structured_candidates", candidate, "structured candidate contains unsupported slot or empty value")
    ids = [str(item).strip() for item in candidate["supporting_card_ids"] if str(item).strip()]
    if not ids or len(set(ids)) != int(candidate["supporting_card_count"]):
        raise _signal_error(path, index, "structured_candidates", candidate, "structured candidate supporting cards are inconsistent")
    if int(candidate["supporting_card_count"]) < int(candidate["aggregation_threshold"]):
        raise _signal_error(path, index, "structured_candidates", candidate, "structured candidate does not meet aggregation threshold")


def _normalize_structured_candidates(signal: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = signal.get("structured_candidates", [])
    normalized = []
    for item in candidates:
        normalized.append(
            {
                "slot": _canonical_string(str(item["slot"])),
                "value": " ".join(str(item["value"]).split()).strip().casefold(),
                "candidate_source": _canonical_string(str(item["candidate_source"])),
                "supporting_card_ids": sorted(set(str(value).strip() for value in item["supporting_card_ids"] if str(value).strip())),
                "supporting_card_count": int(item["supporting_card_count"]),
                "aggregation_threshold": int(item["aggregation_threshold"]),
                "observation_model": str(item["observation_model"]).strip(),
                "evidence_summary": str(item["evidence_summary"]).strip(),
            }
        )
    return normalized
```

然后在 `_validate_signal_record(...)` 与 `_normalize_signal(...)` 中分别调用：

```python
_validate_structured_candidates(path, index, signal, taxonomy)
...
normalized["structured_candidates"] = _normalize_structured_candidates(signal)
```

- [ ] **Step 4: 重新运行 ingestion 聚焦测试，确认通过**

Run: `python -m unittest tests.test_signal_ingestion -v`

Expected:
- `PASS`
- 旧的 phrase-rule 测试不回归
- 新增 structured candidate 校验/normalization 测试通过

- [ ] **Step 5: 提交 ingestion 校验与 normalization 改动**

```bash
git add \
  temu_y2_women/signal_ingestion.py \
  tests/test_signal_ingestion.py
git commit -m "feat: validate and normalize structured signal candidates"
```

## Task 4: 合并文本规则与结构化候选，支持新 value / hybrid provenance

**Files:**
- Modify: `temu_y2_women/signal_ingestion.py`
- Modify: `tests/test_signal_ingestion.py`

- [ ] **Step 1: 先写两个失败测试：新 value 进入 draft、text + structured 同值合并**

```python
def test_ingest_dress_signals_emits_new_value_from_structured_candidates(self) -> None:
    from temu_y2_women.signal_ingestion import ingest_dress_signals

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / "signals.json"
        input_path.write_text(
            json.dumps(
                {
                    "schema_version": "signal-bundle-v1",
                    "signals": [
                        {
                            "signal_id": "dress-image-003",
                            "source_type": "public_roundup_web",
                            "source_url": "https://example.com/roundup",
                            "captured_at": "2026-04-29",
                            "target_market": "US",
                            "category": "dress",
                            "title": "Observed roundup",
                            "summary": "Observed pattern candidate from public cards.",
                            "observed_price_band": "mid",
                            "observed_occasion_tags": ["vacation"],
                            "observed_season_tags": ["summer"],
                            "manual_tags": ["summer", "dress"],
                            "status": "active",
                            "structured_candidates": [
                                {
                                    "slot": "pattern",
                                    "value": "gingham check",
                                    "candidate_source": "roundup_card_image_aggregation",
                                    "supporting_card_ids": ["card-001", "card-002"],
                                    "supporting_card_count": 2,
                                    "aggregation_threshold": 2,
                                    "observation_model": "fake-roundup-observer",
                                    "evidence_summary": "Observed pattern=gingham check across 2 roundup cards.",
                                }
                            ],
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )
        ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")
        draft_elements = _read_json(temp_root / "staged" / "draft_elements.json")["elements"]

    gingham = next(item for item in draft_elements if item["slot"] == "pattern" and item["value"] == "gingham check")
    self.assertEqual(gingham["tags"], [])
    self.assertEqual(gingham["extraction_provenance"]["kind"], "structured-signal-candidate")


def test_ingest_dress_signals_merges_text_and_structured_candidates(self) -> None:
    from temu_y2_women.signal_ingestion import ingest_dress_signals

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / "signals.json"
        input_path.write_text(
            json.dumps(
                {
                    "schema_version": "signal-bundle-v1",
                    "signals": [
                        {
                            "signal_id": "dress-text-001",
                            "source_type": "manual_import",
                            "source_url": "https://example.com/text",
                            "captured_at": "2026-04-29",
                            "target_market": "US",
                            "category": "dress",
                            "title": "Square neckline vacation dress",
                            "summary": "Square neckline cotton poplin dress for summer resort styling.",
                            "observed_price_band": "mid",
                            "observed_occasion_tags": ["resort"],
                            "observed_season_tags": ["summer"],
                            "manual_tags": ["vacation"],
                            "status": "active",
                        },
                        {
                            "signal_id": "dress-image-004",
                            "source_type": "public_roundup_web",
                            "source_url": "https://example.com/roundup",
                            "captured_at": "2026-04-29",
                            "target_market": "US",
                            "category": "dress",
                            "title": "Observed roundup",
                            "summary": "Observed neckline candidate from public cards.",
                            "observed_price_band": "mid",
                            "observed_occasion_tags": ["vacation"],
                            "observed_season_tags": ["summer"],
                            "manual_tags": ["summer", "dress"],
                            "status": "active",
                            "structured_candidates": [
                                {
                                    "slot": "neckline",
                                    "value": "square neckline",
                                    "candidate_source": "roundup_card_image_aggregation",
                                    "supporting_card_ids": ["card-011", "card-014"],
                                    "supporting_card_count": 2,
                                    "aggregation_threshold": 2,
                                    "observation_model": "fake-roundup-observer",
                                    "evidence_summary": "Observed neckline=square neckline across 2 roundup cards.",
                                }
                            ],
                        },
                    ],
                }
            ),
            encoding="utf-8",
        )
        ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")
        draft_elements = _read_json(temp_root / "staged" / "draft_elements.json")["elements"]

    neckline = [item for item in draft_elements if item["slot"] == "neckline" and item["value"] == "square neckline"]
    self.assertEqual(len(neckline), 1)
    self.assertEqual(neckline[0]["extraction_provenance"]["kind"], "hybrid-signal-candidate")
```

- [ ] **Step 2: 运行聚焦测试，确认当前失败**

Run: `python -m unittest tests.test_signal_ingestion.SignalIngestionTest.test_ingest_dress_signals_emits_new_value_from_structured_candidates tests.test_signal_ingestion.SignalIngestionTest.test_ingest_dress_signals_merges_text_and_structured_candidates -v`

Expected:
- `FAIL`
- structured channel 还不会产出 raw candidates
- hybrid 聚合与 provenance 还不存在

- [ ] **Step 3: 实现结构化候选抽取、聚合和 provenance**

在 `temu_y2_women/signal_ingestion.py` 中把现有 `_extract_draft_elements(...)` 拆成文本路与结构化路，并补 tags lookup / score / provenance helper：

```python
def _extract_draft_elements(
    normalized_signals: list[dict[str, Any]],
    rules: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    raw_candidates: list[dict[str, Any]] = []
    signal_outcomes: list[dict[str, Any]] = []
    warnings: list[str] = []
    tag_lookup = _slot_value_tag_lookup(rules)
    for signal in normalized_signals:
        matches = _matching_rules(signal, rules)
        structured = _matching_structured_candidates(signal)
        signal_outcomes.append(_build_signal_outcome(signal, matches, structured))
        if not matches and not structured:
            warnings.append(f"no supported draft candidates extracted for signal {signal['signal_id']}")
            continue
        raw_candidates.extend(_build_rule_raw_candidate(signal, rule) for rule in matches)
        raw_candidates.extend(_build_structured_raw_candidate(signal, item, tag_lookup) for item in structured)
    return _aggregate_draft_elements(raw_candidates), signal_outcomes, warnings


def _build_structured_raw_candidate(
    signal: dict[str, Any],
    candidate: dict[str, Any],
    tag_lookup: dict[tuple[str, str], list[str]],
) -> dict[str, Any]:
    slot = str(candidate["slot"])
    value = str(candidate["value"])
    return {
        "slot": slot,
        "value": value,
        "tags": list(tag_lookup.get((slot, value), [])),
        "price_bands": [signal["observed_price_band"]],
        "occasion_tags": list(signal["observed_occasion_tags"]),
        "season_tags": list(signal["observed_season_tags"]),
        "source_signal_ids": [signal["signal_id"]],
        "rule_matches": [],
        "structured_matches": [
            {
                "signal_id": signal["signal_id"],
                "slot": slot,
                "value": value,
                "candidate_source": candidate["candidate_source"],
                "supporting_card_ids": list(candidate["supporting_card_ids"]),
                "supporting_card_count": candidate["supporting_card_count"],
                "aggregation_threshold": candidate["aggregation_threshold"],
                "observation_model": candidate["observation_model"],
                "evidence_summary": candidate["evidence_summary"],
            }
        ],
    }


def _draft_provenance_kind(group: dict[str, Any]) -> str:
    has_rules = bool(group["rule_matches"])
    has_structured = bool(group["structured_matches"])
    if has_rules and has_structured:
        return "hybrid-signal-candidate"
    if has_structured:
        return "structured-signal-candidate"
    return "signal-rule-match"
```

同时更新 `_empty_element_group(...)`、`_merge_candidate_group(...)`、`_build_draft_element(...)` 和 `_build_signal_outcome(...)`，让它们显式处理：

- `structured_matches`
- `matched_channels`
- `matched_structured_keys`
- `suggested_base_score`
- hybrid / structured-only `evidence_summary`

- [ ] **Step 4: 运行完整 ingestion 测试，确认全部通过**

Run: `python -m unittest tests.test_signal_ingestion -v`

Expected:
- `PASS`
- 旧的 phrase-rule 回归继续通过
- 新 value / hybrid / matched_channels 断言通过

- [ ] **Step 5: 提交双通道抽取改动**

```bash
git add \
  temu_y2_women/signal_ingestion.py \
  tests/test_signal_ingestion.py
git commit -m "feat: merge structured and text signal candidates"
```

## Task 5: 用 mixed-source refresh 验证“新 value 仅靠图片链路入 draft”

**Files:**
- Modify: `tests/test_public_signal_refresh.py`
- Modify: `tests/fixtures/public_refresh/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-ingestion-report.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`

- [ ] **Step 1: 先写 mixed-source 集成失败测试**

```python
def test_run_public_signal_refresh_promotes_new_structured_value_into_drafts(self) -> None:
    from tempfile import TemporaryDirectory
    from temu_y2_women.public_signal_refresh import run_public_signal_refresh

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        registry_path = temp_root / "registry.json"
        registry_path.write_text(json.dumps(_mixed_source_registry()), encoding="utf-8")

        result = run_public_signal_refresh(
            registry_path=registry_path,
            output_root=temp_root / "runs",
            fetched_at="2026-04-29T00:00:00Z",
            fetcher=_mixed_registry_fetcher(),
            card_image_observer=_fake_card_observer_with_new_value,
        )

        run_dir = temp_root / "runs" / result["run_id"]
        draft_elements = _read_json(run_dir / "draft_elements.json")["elements"]
        ingestion_report = _read_json(run_dir / "ingestion_report.json")

    gingham = next(item for item in draft_elements if item["slot"] == "pattern" and item["value"] == "gingham check")
    self.assertEqual(gingham["tags"], [])
    outcome = next(item for item in ingestion_report["signal_outcomes"] if item["signal_id"].endswith("pattern-gingham-check-001"))
    self.assertEqual(outcome["matched_channels"], ["structured_candidate"])
```

- [ ] **Step 2: 跑聚焦 refresh 集成测试，确认当前失败**

Run: `python -m unittest tests.test_public_signal_refresh.PublicSignalRefreshTest.test_run_public_signal_refresh_promotes_new_structured_value_into_drafts -v`

Expected:
- `FAIL`
- 当前 refresh run 还无法让新 value 只靠 structured channel 入 draft

- [ ] **Step 3: 更新 fake observer 与 refresh fixture，固定最终闭环产物**

在 `tests/test_public_signal_refresh.py` 中新增一个专用 fake observer：

```python
def _fake_card_observer_with_new_value(card: dict[str, object]) -> dict[str, object]:
    if str(card["card_id"]).endswith("001"):
        return {
            "observed_slots": [
                {"slot": "pattern", "value": "gingham check", "evidence_summary": "small two-tone checks repeat across the dress"},
                {"slot": "dress_length", "value": "mini", "evidence_summary": "hemline ends above knee"},
            ],
            "abstained_slots": ["opacity_level"],
            "warnings": [],
        }
    return {
        "observed_slots": [
            {"slot": "pattern", "value": "gingham check", "evidence_summary": "same check pattern repeats across the body"},
        ],
        "abstained_slots": ["waistline", "opacity_level"],
        "warnings": [],
    }
```

然后更新 public refresh fixtures，使其稳定反映：

- `normalized_signals.json` 的 roundup signal 包含 `structured_candidates`
- `draft_elements.json` 新增 `pattern=gingham check`
- `ingestion_report.json` 对该 signal 记录 `matched_channels=["structured_candidate"]`
- `refresh_report.json` coverage / warnings 与新 signal 计数一致

- [ ] **Step 4: 运行 refresh 测试与关键回归**

Run: `python -m unittest tests.test_public_signal_refresh tests.test_roundup_canonical_signal_builder tests.test_signal_ingestion -v`

Expected:
- `PASS`
- mixed-source 新 value 集成测试通过
- builder / ingestion / refresh 三段回归全部通过

- [ ] **Step 5: 提交集成闭环与 fixture 更新**

```bash
git add \
  tests/test_public_signal_refresh.py \
  tests/fixtures/public_refresh/dress/expected-normalized-signals.json \
  tests/fixtures/public_refresh/dress/expected-draft-elements.json \
  tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json \
  tests/fixtures/public_refresh/dress/expected-ingestion-report.json \
  tests/fixtures/public_refresh/dress/expected-refresh-report.json
git commit -m "test: cover structured image candidate refresh flow"
```

## Task 6: 全量验证并准备进入实现集成

**Files:**
- Modify: `temu_y2_women/roundup_canonical_signal_builder.py`
- Modify: `temu_y2_women/public_signal_refresh.py`
- Modify: `temu_y2_women/signal_ingestion.py`
- Modify: `tests/test_roundup_canonical_signal_builder.py`
- Modify: `tests/test_public_signal_refresh.py`
- Modify: `tests/test_signal_ingestion.py`
- Modify: `tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-ingestion-report.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`

- [ ] **Step 1: 运行目标测试组**

Run: `python -m unittest tests.test_roundup_canonical_signal_builder tests.test_public_signal_refresh tests.test_signal_ingestion -v`

Expected:
- `PASS`
- 结构化候选 builder / refresh / ingestion 三段测试全部通过

- [ ] **Step 2: 运行全量单测**

Run: `python -m unittest -v`

Expected:
- `PASS`
- 全仓测试无回归

- [ ] **Step 3: 运行仓库规则校验**

Run: `python validate_python_function_length.py .`
Expected: `OK`

Run: `python validate_forbidden_patterns.py .`
Expected: `OK`

- [ ] **Step 4: 提交最终集成结果**

```bash
git add \
  temu_y2_women/roundup_canonical_signal_builder.py \
  temu_y2_women/public_signal_refresh.py \
  temu_y2_women/signal_ingestion.py \
  tests/test_roundup_canonical_signal_builder.py \
  tests/test_public_signal_refresh.py \
  tests/test_signal_ingestion.py \
  tests/fixtures/public_sources/dress/expected-whowhatwear-best-summer-dresses-2025-canonical-signals.json \
  tests/fixtures/public_refresh/dress/expected-normalized-signals.json \
  tests/fixtures/public_refresh/dress/expected-draft-elements.json \
  tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json \
  tests/fixtures/public_refresh/dress/expected-ingestion-report.json \
  tests/fixtures/public_refresh/dress/expected-refresh-report.json
git commit -m "feat: ingest structured image signal candidates"
```

## Self-Review Checklist

- Spec coverage:
  - `structured_candidates` contract -> Task 1 / Task 2
  - ingestion dual-channel validation / normalization -> Task 3
  - new value / hybrid provenance / matched_channels -> Task 4
  - mixed-source refresh proof -> Task 5
  - full verification -> Task 6
- Placeholder scan:
  - 无占位标记或延后实现表述
  - 每个任务都带测试、命令、代码片段、提交命令
- Type consistency:
  - `structured_candidates`
  - `candidate_source`
  - `supporting_card_ids`
  - `supporting_card_count`
  - `aggregation_threshold`
  - `matched_channels`
  - `structured-signal-candidate`
  - `hybrid-signal-candidate`

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-29-image-structured-signal-ingestion.md`.

Two execution options:

1. **Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

Given your earlier preference for multi-agent collaboration, default to **Subagent-Driven** unless you explicitly switch to Inline.
