# Refresh New Slot Extraction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让新增的客观 dress slot 不只停留在手工 baseline，而是能从公开 source / signal bundle 中被抽取、进入 draft evidence、通过 promotion，并在 refresh 实验中产生可观测变化。

**Architecture:** 先扩 `signal_phrase_rules.json` 与 manual signal fixtures，让 `signal_ingestion.py` 能直接产出新 slot draft elements；再更新 canonical/public refresh fixture 及测试，让公开 editorial 文本也能命中新 slot；最后补 promotion / refresh experiment 的新 slot 场景，验证从 draft 到 active 到实验报告的闭环。

**Tech Stack:** Python 3、JSON fixture authoring、现有 `signal_ingestion.py` / `canonical_signal_builder.py` / `public_signal_refresh.py` / `evidence_promotion.py`、`unittest`。

---

## File Map

- Modify: `data/ingestion/dress/signal_phrase_rules.json`
- Modify: `tests/fixtures/signals/dress/valid-signal-bundle.json`
- Modify: `tests/fixtures/signals/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/signals/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/signals/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/signals/dress/expected-ingestion-report.json`
- Modify: `tests/test_signal_ingestion.py`
- Modify: `tests/test_canonical_signal_builder.py`
- Modify: `tests/fixtures/public_sources/dress/expected-canonical-signals.json`
- Modify: `tests/fixtures/public_sources/dress/expected-signal-bundle.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-ingestion-report.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`
- Modify: `tests/test_public_signal_refresh.py`
- Modify: `tests/test_evidence_promotion.py`
- Modify: `tests/test_refresh_experiment_runner.py`
- Create: `tests/fixtures/promotion/dress/objective_slots/draft_elements.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/draft_strategy_hints.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/reviewed_decisions.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/expected_elements_after_apply.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/expected_strategy_templates_after_apply.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/expected_promotion_report.json`

### Task 1: 扩 signal phrase rules，并让 manual signal ingestion 产出新 slot

**Files:**
- Modify: `data/ingestion/dress/signal_phrase_rules.json`
- Modify: `tests/fixtures/signals/dress/valid-signal-bundle.json`
- Modify: `tests/fixtures/signals/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/signals/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/signals/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/signals/dress/expected-ingestion-report.json`
- Modify: `tests/test_signal_ingestion.py`

- [ ] **Step 1: 先写 signal ingestion 失败测试**

```python
def test_ingest_dress_signals_emits_objective_slot_drafts(self) -> None:
    from temu_y2_women.signal_ingestion import ingest_dress_signals

    with TemporaryDirectory() as temp_dir:
        output_dir = Path(temp_dir)
        ingest_dress_signals(
            input_path=_SIGNAL_FIXTURE_DIR / "valid-signal-bundle.json",
            output_dir=output_dir,
        )
        draft_elements = _read_json(output_dir / "draft_elements.json")["elements"]

    by_slot_value = {(item["slot"], item["value"]) for item in draft_elements}
    self.assertIn(("dress_length", "mini"), by_slot_value)
    self.assertIn(("color_family", "white"), by_slot_value)
    self.assertIn(("print_scale", "micro print"), by_slot_value)
    self.assertIn(("opacity_level", "sheer"), by_slot_value)
    self.assertIn(("waistline", "drop waist"), by_slot_value)
```

- [ ] **Step 2: 跑聚焦 ingestion 测试，确认当前失败**

Run: `python -m unittest tests.test_signal_ingestion.SignalIngestionTest.test_ingest_dress_signals_emits_objective_slot_drafts -v`

Expected:
- `FAIL`
- 当前 phrase rules 无法为新 slot 产出 draft elements

- [ ] **Step 3: 实现 phrase rules 与 manual signal fixture 扩展**

```json
{
  "slot": "dress_length",
  "value": "mini",
  "phrases": ["mini", "minis"],
  "tags": ["summer", "vacation", "mini"]
}
```

```json
{
  "slot": "waistline",
  "value": "drop waist",
  "phrases": ["drop-waist", "drop waist"],
  "tags": ["summer", "drop-waist", "feminine"]
}
```

```json
{
  "slot": "color_family",
  "value": "white",
  "phrases": ["white dress", "white dresses"],
  "tags": ["summer", "white", "vacation"]
}
```

```json
{
  "slot": "print_scale",
  "value": "micro print",
  "phrases": ["micro-dot", "micro dot", "micro print"],
  "tags": ["summer", "micro-print", "dress"]
}
```

```json
{
  "slot": "opacity_level",
  "value": "sheer",
  "phrases": ["sheer"],
  "tags": ["summer", "sheer", "feminine"]
}
```

```json
{
  "signal_id": "dress-signal-001",
  "title": "Summer Vacation White Mini Dress",
  "summary": "White mini cotton poplin dress with square neckline, flutter sleeves, micro-dot print, and sheer overlay finish.",
  "manual_tags": ["feminine", "summer", "white"]
}
```

- [ ] **Step 4: 重跑 signal ingestion 测试**

Run: `python -m unittest tests.test_signal_ingestion -v`

Expected:
- `PASS`
- `expected-draft-elements.json` / `expected-draft-strategy-hints.json` 中出现新 slot draft

- [ ] **Step 5: 提交 signal ingestion 扩展**

```bash
git add data/ingestion/dress/signal_phrase_rules.json tests/fixtures/signals/dress/valid-signal-bundle.json tests/fixtures/signals/dress/expected-normalized-signals.json tests/fixtures/signals/dress/expected-draft-elements.json tests/fixtures/signals/dress/expected-draft-strategy-hints.json tests/fixtures/signals/dress/expected-ingestion-report.json tests/test_signal_ingestion.py
git commit -m "feat(ingestion): extract objective dress slots from signals"
```

### Task 2: 扩 canonical/public refresh 覆盖，让公开 editorial 文本命中新 slot

**Files:**
- Modify: `tests/test_canonical_signal_builder.py`
- Modify: `tests/fixtures/public_sources/dress/expected-canonical-signals.json`
- Modify: `tests/fixtures/public_sources/dress/expected-signal-bundle.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-normalized-signals.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-elements.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-ingestion-report.json`
- Modify: `tests/fixtures/public_refresh/dress/expected-refresh-report.json`
- Modify: `tests/test_public_signal_refresh.py`

- [ ] **Step 1: 先写 canonical / refresh 失败测试**

```python
def test_phrase_rule_aliases_cover_objective_slot_editorial_variants(self) -> None:
    rules = json.loads(Path("data/ingestion/dress/signal_phrase_rules.json").read_text(encoding="utf-8"))
    by_value = {rule["value"]: rule for rule in rules["slot_value_rules"]}

    self.assertIn("minis", by_value["mini"]["phrases"])
    self.assertIn("drop-waist", by_value["drop waist"]["phrases"])
    self.assertIn("white dresses", by_value["white"]["phrases"])
    self.assertIn("micro-dot", by_value["micro print"]["phrases"])
    self.assertIn("sheer", by_value["sheer"]["phrases"])
```

```python
def test_bundle_can_flow_into_existing_signal_ingestion(self) -> None:
    from temu_y2_women.canonical_signal_builder import build_canonical_signals, build_signal_bundle
    from temu_y2_women.signal_ingestion import ingest_dress_signals

    snapshot = _load_snapshot()
    canonical_payload = build_canonical_signals(snapshot=snapshot, default_price_band="mid")
    signal_bundle = build_signal_bundle(canonical_payload)

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        input_path = temp_root / "signal_bundle.json"
        input_path.write_text(json.dumps(signal_bundle), encoding="utf-8")
        result = ingest_dress_signals(input_path=input_path, output_dir=temp_root / "staged")

    self.assertEqual(
        result["coverage"]["matched_signal_ids"],
        [
            "whowhatwear-summer-2025-dress-trends-the-vacation-mini-001",
            "whowhatwear-summer-2025-dress-trends-fairy-sleeves-002",
            "whowhatwear-summer-2025-dress-trends-all-things-polka-dots-003",
            "whowhatwear-summer-2025-dress-trends-the-exaggerated-drop-waist-004",
            "whowhatwear-summer-2025-dress-trends-sheer-printed-midis-005",
        ],
    )
```

```python
def test_run_public_signal_refresh_supports_all_configured_sources(self) -> None:
    from temu_y2_women.public_signal_refresh import run_public_signal_refresh

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        result = run_public_signal_refresh(
            registry_path=Path("data/refresh/dress/source_registry.json"),
            output_root=temp_root,
            fetched_at="2026-04-28T00:00:00Z",
            fetcher=_full_registry_fetcher(),
        )

    self.assertGreaterEqual(result["coverage"]["matched_signals"], 13)
    self.assertEqual(
        [item["matched_signal_count"] for item in result["source_details"]],
        [5, 4, 4],
    )
```

- [ ] **Step 2: 跑 canonical / refresh 聚焦测试，确认当前失败**

Run:

```bash
python -m unittest tests.test_canonical_signal_builder tests.test_public_signal_refresh -v
```

Expected:
- `FAIL`
- 当前公开 source 只会命中旧 slot，matched count 不足

- [ ] **Step 3: 更新 canonical/public refresh fixtures**

```json
{
  "signal_id": "whowhatwear-summer-2025-dress-trends-the-vacation-mini-001",
  "title": "The Vacation Mini",
  "summary": "This trend brings pure serotonin. Think dazzling materials, smocked bodices, halter ties, and prints that look like they belong in a cocktail glass.",
  "manual_tags": ["summer", "vacation"]
}
```

```json
{
  "signal_id": "whowhatwear-summer-2025-dress-trends-all-things-polka-dots-003",
  "title": "All Things Polka Dots",
  "summary": "Yes, polka dots are trending again. Whether you go micro-dot or oversize print, a dotted dress instantly adds charm.",
  "manual_tags": ["summer"]
}
```

```json
{
  "signal_id": "whowhatwear-summer-2025-dress-trends-the-exaggerated-drop-waist-004",
  "title": "The Exaggerated Drop Waist",
  "summary": "Drop-waist dresses with dramatic volume or structure are popping up everywhere.",
  "manual_tags": ["summer"]
}
```

```json
{
  "signal_id": "whowhatwear-summer-2025-dress-trends-sheer-printed-midis-005",
  "title": "Sheer Printed Midis",
  "summary": "Sheer printed dresses strike a balance between playful and polished.",
  "manual_tags": ["summer"]
}
```

- [ ] **Step 4: 重跑 canonical / refresh 测试**

Run:

```bash
python -m unittest tests.test_canonical_signal_builder tests.test_public_signal_refresh -v
```

Expected:
- `PASS`
- 单源与多源 refresh 的 matched counts 提升
- `expected-refresh-report.json` / staged artifacts 与新 slot 对齐

- [ ] **Step 5: 提交公开 source 抽取扩展**

```bash
git add tests/test_canonical_signal_builder.py tests/fixtures/public_sources/dress/expected-canonical-signals.json tests/fixtures/public_sources/dress/expected-signal-bundle.json tests/fixtures/public_refresh/dress/expected-normalized-signals.json tests/fixtures/public_refresh/dress/expected-draft-elements.json tests/fixtures/public_refresh/dress/expected-draft-strategy-hints.json tests/fixtures/public_refresh/dress/expected-ingestion-report.json tests/fixtures/public_refresh/dress/expected-refresh-report.json tests/test_public_signal_refresh.py
git commit -m "feat(refresh): map objective slots from public sources"
```

### Task 3: 验证 promotion / refresh experiment 能接住新 slot

**Files:**
- Modify: `tests/test_evidence_promotion.py`
- Modify: `tests/test_refresh_experiment_runner.py`
- Create: `tests/fixtures/promotion/dress/objective_slots/draft_elements.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/draft_strategy_hints.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/reviewed_decisions.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/expected_elements_after_apply.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/expected_strategy_templates_after_apply.json`
- Create: `tests/fixtures/promotion/dress/objective_slots/expected_promotion_report.json`

- [ ] **Step 1: 先写 promotion / experiment 失败测试**

```python
def test_apply_reviewed_dress_promotion_accepts_objective_slot_elements(self) -> None:
    from temu_y2_women.evidence_promotion import apply_reviewed_dress_promotion

    with TemporaryDirectory() as temp_dir:
        temp_root = Path(temp_dir)
        elements_path, strategies_path = _seed_active_evidence(temp_root)
        result = apply_reviewed_dress_promotion(
            draft_elements_path=Path("tests/fixtures/promotion/dress/objective_slots/draft_elements.json"),
            draft_strategy_hints_path=Path("tests/fixtures/promotion/dress/objective_slots/draft_strategy_hints.json"),
            reviewed_path=Path("tests/fixtures/promotion/dress/objective_slots/reviewed_decisions.json"),
            active_elements_path=elements_path,
            active_strategies_path=strategies_path,
            report_path=temp_root / "promotion_report.json",
            taxonomy_path=Path("data/mvp/dress/evidence_taxonomy.json"),
        )

    self.assertEqual(result["summary"]["elements"]["accepted"], 3)
    self.assertEqual(result["summary"]["strategy_hints"]["accepted"], 1)
```

```python
def test_apply_refresh_experiment_reports_objective_slot_changes(self) -> None:
    prepared = _prepare_refresh_experiment(
        scenario="create",
        request_entries=[("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
    )
    review_path = Path(prepared["promotion_review_path"])
    review_payload = _read_json(review_path)
    review_payload["element_reviews"][0]["decision"] = "accept"
    review_payload["strategy_reviews"][0]["decision"] = "accept"
    _write_json(review_path, review_payload)

    result = apply_refresh_experiment(
        manifest_path=Path(prepared["manifest_path"]),
        reviewed_path=review_path,
    )

    report = _read_json(Path(result["experiment_report_path"]))
    self.assertIn("dress_length", report["slot_change_summary"])
    self.assertIn("waistline", report["slot_change_summary"])
```

- [ ] **Step 2: 跑 promotion / experiment 聚焦测试，确认当前失败**

Run:

```bash
python -m unittest tests.test_evidence_promotion tests.test_refresh_experiment_runner -v
```

Expected:
- `FAIL`
- 现有 fixtures 不包含新 slot promotion 场景

- [ ] **Step 3: 实现 objective slot promotion fixtures**

```json
{
  "draft_id": "draft-dress_length-mini",
  "category": "dress",
  "slot": "dress_length",
  "value": "mini",
  "tags": ["summer", "vacation", "mini"],
  "price_bands": ["mid"],
  "occasion_tags": ["vacation"],
  "season_tags": ["summer"],
  "risk_flags": [],
  "suggested_base_score": 0.75,
  "evidence_summary": "Derived from repeated public summer-vacation mentions of mini dress proportion.",
  "status": "draft"
}
```

```json
{
  "hint_id": "draft-strategy-us-summer-vacation-objective-slots",
  "category": "dress",
  "target_market": "US",
  "season_tags": ["summer"],
  "occasion_tags": ["vacation"],
  "boost_tags": ["summer", "vacation", "white"],
  "slot_preferences": {
    "dress_length": ["mini"],
    "waistline": ["drop waist"],
    "color_family": ["white"]
  },
  "priority_signal": 3,
  "status": "draft"
}
```

```json
{
  "elements": [
    {
      "draft_id": "draft-dress_length-mini",
      "decision": "accept",
      "proposed_element": {
        "element_id": "dress-length-mini-001",
        "slot": "dress_length",
        "value": "mini"
      }
    }
  ],
  "strategy_hints": [
    {
      "hint_id": "draft-strategy-us-summer-vacation-objective-slots",
      "decision": "accept"
    }
  ]
}
```

- [ ] **Step 4: 重跑 promotion / experiment 测试**

Run:

```bash
python -m unittest tests.test_evidence_promotion tests.test_refresh_experiment_runner -v
```

Expected:
- `PASS`
- objective slot draft 能成功进入 active evidence
- refresh experiment 能在 `slot_change_summary` 中看到新 slot 变化

- [ ] **Step 5: 提交 promotion / experiment 兼容**

```bash
git add tests/test_evidence_promotion.py tests/test_refresh_experiment_runner.py tests/fixtures/promotion/dress/objective_slots/draft_elements.json tests/fixtures/promotion/dress/objective_slots/draft_strategy_hints.json tests/fixtures/promotion/dress/objective_slots/reviewed_decisions.json tests/fixtures/promotion/dress/objective_slots/expected_elements_after_apply.json tests/fixtures/promotion/dress/objective_slots/expected_strategy_templates_after_apply.json tests/fixtures/promotion/dress/objective_slots/expected_promotion_report.json
git commit -m "feat(promotion): support objective slot refresh evidence"
```

### Task 4: 回归验证与交付收口

**Files:**
- Modify: `data/ingestion/dress/signal_phrase_rules.json`（仅当验证暴露边角问题）
- Modify: `tests/test_signal_ingestion.py`
- Modify: `tests/test_canonical_signal_builder.py`
- Modify: `tests/test_public_signal_refresh.py`
- Modify: `tests/test_evidence_promotion.py`
- Modify: `tests/test_refresh_experiment_runner.py`

- [ ] **Step 1: 跑本 change 相关回归**

Run:

```bash
python -m unittest tests.test_signal_ingestion tests.test_canonical_signal_builder tests.test_public_signal_refresh tests.test_evidence_promotion tests.test_refresh_experiment_runner -v
python -m py_compile temu_y2_women/signal_ingestion.py tests/test_signal_ingestion.py tests/test_canonical_signal_builder.py tests/test_public_signal_refresh.py tests/test_evidence_promotion.py tests/test_refresh_experiment_runner.py
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- 所有相关测试通过
- `py_compile` 无输出
- 函数长度校验 `OK`

- [ ] **Step 2: 若验证失败，只做最小修复**

```python
def _build_slot_preferences(draft_elements: list[dict[str, Any]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = {}
    for element in draft_elements:
        grouped.setdefault(str(element["slot"]), []).append(str(element["value"]))
    return {slot: sorted(set(values)) for slot, values in sorted(grouped.items())}
```

- [ ] **Step 3: 确认 diff 只覆盖 refresh 新 slot 抽取范围**

```bash
git status --short
git diff --stat
```

Expected:
- 只涉及 phrase rules、fixtures、refresh / promotion / experiment 相关测试
- 不混入 Change A 的 composition / prompt 代码

- [ ] **Step 4: 最终整理提交**

```bash
git log --oneline --decorate -5
```

Expected:
- 最近提交形成一组清晰的 refresh new-slot extraction feature commits

- [ ] **Step 5: 推送分支**

```bash
git push -u origin codex/refresh-new-slot-extraction
```

Expected:
- 远端分支创建成功
- 后续用 `git-pr-ship` 创建 PR，不直接推 `main`
