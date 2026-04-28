# Objective Slot Baseline + Composition + Prompt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 把 `dress` 主链从“少量旧 slot 的保守组合”升级成“包含 5 个新增客观 slot 的可解释概念与 prompt 输出”，直接拉开概念与成图差异。

**Architecture:** 先扩 evidence taxonomy、active elements、strategy templates，建立可运行的客观 slot baseline；再在 `composition_engine.py` 中把新 slot 分成“结构型 top-1 optional”与“pattern/print/detail 小搜索组”；最后把新 slot 显式喂给 `prompt_renderer.py` 与 `factory_spec_builder.py`，确保变化真正进入图像与工厂草案层。

**Tech Stack:** Python 3、JSON evidence stores、现有 `unittest` 测试体系、现有 `GenerationError` / evidence validation、PowerShell 验证命令。

---

## File Map

- Modify: `data/mvp/dress/evidence_taxonomy.json`
- Modify: `data/mvp/dress/elements.json`
- Modify: `data/mvp/dress/strategy_templates.json`
- Modify: `tests/test_evidence_repository.py`
- Modify: `temu_y2_women/composition_engine.py`
- Modify: `tests/test_composition_engine.py`
- Modify: `temu_y2_women/prompt_renderer.py`
- Modify: `tests/test_prompt_renderer.py`
- Modify: `temu_y2_women/factory_spec_builder.py`
- Modify: `tests/test_factory_spec_builder.py`

### Task 1: 扩 taxonomy、active elements、strategy templates 基线

**Files:**
- Modify: `data/mvp/dress/evidence_taxonomy.json`
- Modify: `data/mvp/dress/elements.json`
- Modify: `data/mvp/dress/strategy_templates.json`
- Modify: `tests/test_evidence_repository.py`

- [ ] **Step 1: 先写 evidence runtime 基线失败测试**

```python
def test_runtime_dress_evidence_includes_objective_slots(self) -> None:
    from pathlib import Path

    from temu_y2_women.evidence_repository import load_elements, load_strategy_templates

    taxonomy_path = Path("data/mvp/dress/evidence_taxonomy.json")
    elements_path = Path("data/mvp/dress/elements.json")
    strategies_path = Path("data/mvp/dress/strategy_templates.json")

    elements = load_elements(elements_path, taxonomy_path=taxonomy_path)
    active_by_slot = {}
    for element in elements:
        if element["status"] != "active":
            continue
        active_by_slot.setdefault(element["slot"], set()).add(element["value"])

    self.assertEqual(active_by_slot["dress_length"], {"mini", "midi"})
    self.assertEqual(active_by_slot["waistline"], {"natural waist", "drop waist"})
    self.assertEqual(active_by_slot["color_family"], {"white", "red"})
    self.assertEqual(active_by_slot["print_scale"], {"micro print", "oversized print"})
    self.assertEqual(active_by_slot["opacity_level"], {"opaque", "sheer"})
    self.assertIn("polka dot", active_by_slot["pattern"])
    self.assertIn("neck scarf", active_by_slot["detail"])

    strategies = load_strategy_templates(
        strategies_path,
        taxonomy_path=taxonomy_path,
        elements_path=elements_path,
    )
    vacation = next(item for item in strategies if item["strategy_id"] == "dress-us-summer-vacation")
    self.assertEqual(vacation["slot_preferences"]["dress_length"], ["mini", "midi"])
    self.assertEqual(vacation["slot_preferences"]["waistline"], ["drop waist"])
    self.assertEqual(vacation["slot_preferences"]["color_family"], ["white", "red"])
```

- [ ] **Step 2: 跑聚焦单测，确认当前失败**

Run: `python -m unittest tests.test_evidence_repository.EvidenceRepositoryValidationTest.test_runtime_dress_evidence_includes_objective_slots -v`

Expected:
- `FAIL`
- 报 `KeyError: 'dress_length'` 或 runtime evidence 缺少新增 slot/value

- [ ] **Step 3: 实现 taxonomy、elements、strategy 基线**

```json
{
  "allowed_slots": [
    "silhouette",
    "fabric",
    "neckline",
    "sleeve",
    "pattern",
    "detail",
    "dress_length",
    "waistline",
    "color_family",
    "print_scale",
    "opacity_level"
  ],
  "allowed_tags": [
    "airy",
    "bodycon",
    "breathable",
    "comfort",
    "dress",
    "drop-waist",
    "feminine",
    "floral",
    "micro-print",
    "midi",
    "mini",
    "opaque",
    "oversized-print",
    "polka-dot",
    "red",
    "scarf",
    "sheer",
    "summer",
    "vacation",
    "white"
  ]
}
```

```json
{
  "element_id": "dress-length-mini-001",
  "category": "dress",
  "slot": "dress_length",
  "value": "mini",
  "tags": ["summer", "vacation", "mini"],
  "base_score": 0.79,
  "price_bands": ["mid"],
  "occasion_tags": ["vacation", "casual"],
  "season_tags": ["spring", "summer"],
  "risk_flags": [],
  "evidence_summary": "Mini length remains a strong summer shape with clear resort and vacation visibility.",
  "status": "active"
}
```

```json
{
  "element_id": "dress-waistline-drop-waist-001",
  "category": "dress",
  "slot": "waistline",
  "value": "drop waist",
  "tags": ["summer", "drop-waist", "feminine"],
  "base_score": 0.81,
  "price_bands": ["mid"],
  "occasion_tags": ["vacation", "casual"],
  "season_tags": ["spring", "summer"],
  "risk_flags": [],
  "evidence_summary": "Drop-waist structure is resurfacing as a visible silhouette update in current dress editorials.",
  "status": "active"
}
```

```json
"slot_preferences": {
  "silhouette": ["a-line"],
  "fabric": ["cotton poplin"],
  "neckline": ["square neckline"],
  "sleeve": ["flutter sleeve"],
  "dress_length": ["mini", "midi"],
  "waistline": ["drop waist"],
  "color_family": ["white", "red"],
  "pattern": ["floral print", "polka dot"],
  "print_scale": ["micro print", "oversized print"],
  "opacity_level": ["opaque", "sheer"],
  "detail": ["smocked bodice", "neck scarf"]
}
```

- [ ] **Step 4: 重跑 evidence 相关测试**

Run: `python -m unittest tests.test_evidence_repository -v`

Expected:
- `PASS`
- runtime evidence validation 接受新增 slot / tag / strategy preferences

- [ ] **Step 5: 提交 baseline evidence 变更**

```bash
git add data/mvp/dress/evidence_taxonomy.json data/mvp/dress/elements.json data/mvp/dress/strategy_templates.json tests/test_evidence_repository.py
git commit -m "feat(evidence): expand objective dress slot baseline"
```

### Task 2: 扩展组合器，让新 slot 真正进入 selected_elements

**Files:**
- Modify: `temu_y2_women/composition_engine.py`
- Modify: `tests/test_composition_engine.py`

- [ ] **Step 1: 先写组合器失败测试**

```python
def test_selects_new_objective_slots_for_a_line_vacation_concept(self) -> None:
    from temu_y2_women.composition_engine import compose_concept

    request = _request()
    candidates = {
        "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "dress_length": [
            _candidate("dress-length-mini-001", "dress_length", "mini", 0.81, ("mini",)),
            _candidate("dress-length-midi-001", "dress_length", "midi", 0.78, ("midi",)),
        ],
        "waistline": [_candidate("dress-waistline-drop-waist-001", "waistline", "drop waist", 0.82, ("drop-waist",))],
        "color_family": [_candidate("dress-color-family-white-001", "color_family", "white", 0.8, ("white",))],
        "opacity_level": [_candidate("dress-opacity-level-sheer-001", "opacity_level", "sheer", 0.74, ("sheer",))],
        "pattern": [_candidate("dress-pattern-polka-dot-001", "pattern", "polka dot", 0.77, ("polka-dot",))],
        "print_scale": [_candidate("dress-print-scale-micro-print-001", "print_scale", "micro print", 0.75, ("micro-print",))],
    }

    concept = compose_concept(request, candidates)

    self.assertEqual(concept.selected_elements["dress_length"].value, "mini")
    self.assertEqual(concept.selected_elements["waistline"].value, "drop waist")
    self.assertEqual(concept.selected_elements["color_family"].value, "white")
    self.assertEqual(concept.selected_elements["opacity_level"].value, "sheer")
    self.assertEqual(concept.selected_elements["pattern"].value, "polka dot")
    self.assertEqual(concept.selected_elements["print_scale"].value, "micro print")
```

```python
def test_omits_print_scale_when_pattern_is_missing(self) -> None:
    from temu_y2_women.composition_engine import compose_concept

    request = _request()
    candidates = {
        "silhouette": [_candidate("dress-silhouette-a-line-001", "silhouette", "a-line", 0.91, ("summer",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "print_scale": [_candidate("dress-print-scale-micro-print-001", "print_scale", "micro print", 0.75, ("micro-print",))],
    }

    concept = compose_concept(request, candidates)

    self.assertNotIn("print_scale", concept.selected_elements)
```

```python
def test_prefers_natural_waist_when_drop_waist_conflicts_with_bodycon(self) -> None:
    from temu_y2_women.composition_engine import compose_concept

    request = _request()
    candidates = {
        "silhouette": [_candidate("dress-silhouette-bodycon-001", "silhouette", "bodycon", 0.9, ("bodycon",))],
        "fabric": [_candidate("dress-fabric-cotton-poplin-001", "fabric", "cotton poplin", 0.89, ("lightweight",))],
        "waistline": [
            _candidate("dress-waistline-drop-waist-001", "waistline", "drop waist", 0.84, ("drop-waist",)),
            _candidate("dress-waistline-natural-waist-001", "waistline", "natural waist", 0.74, ("feminine",)),
        ],
    }

    concept = compose_concept(request, candidates)

    self.assertEqual(concept.selected_elements["waistline"].value, "natural waist")
    self.assertIn("structural conflict avoided: bodycon + drop waist", concept.constraint_notes)
```

- [ ] **Step 2: 跑聚焦组合测试，确认当前失败**

Run: `python -m unittest tests.test_composition_engine -v`

Expected:
- `FAIL`
- 新 slot 不会进入 `selected_elements`
- `print_scale` 目前不会做依赖控制
- `bodycon + drop waist` 目前不会做结构冲突处理

- [ ] **Step 3: 实现新 slot 组合逻辑**

```python
_STANDARD_OPTIONAL_SLOTS = (
    "neckline",
    "sleeve",
    "dress_length",
    "waistline",
    "color_family",
    "opacity_level",
)
_SURFACE_TOP_K = 3
```

```python
def _select_standard_optional_slots(
    parsed_candidates: dict[str, list[CandidateElement]],
    required_selected: dict[str, CandidateElement],
) -> tuple[dict[str, CandidateElement], tuple[str, ...]]:
    selected: dict[str, CandidateElement] = {}
    notes: list[str] = []
    for slot in _STANDARD_OPTIONAL_SLOTS:
        ranked = _top_candidates(parsed_candidates.get(slot, []), limit=3)
        chosen = _first_eligible_optional(slot, ranked, {**required_selected, **selected}, notes)
        if chosen is not None:
            selected[slot] = chosen
    return selected, tuple(notes)
```

```python
def _first_eligible_optional(
    slot: str,
    ranked: list[CandidateElement],
    selected: dict[str, CandidateElement],
    notes: list[str],
) -> CandidateElement | None:
    for candidate in ranked:
        if slot == "waistline" and _selected_value(selected, "silhouette") == "bodycon" and candidate.value == "drop waist":
            notes.append("structural conflict avoided: bodycon + drop waist")
            continue
        return candidate
    return None
```

```python
def _select_surface_group(
    parsed_candidates: dict[str, list[CandidateElement]],
    rules: tuple[CompatibilityRule, ...],
) -> tuple[dict[str, CandidateElement], CompatibilityEvaluation]:
    best_selected: dict[str, CandidateElement] = {}
    best_evaluation = CompatibilityEvaluation((), (), 0.0, ())
    best_rank = _selection_rank(best_selected, best_evaluation)
    pattern_options = [None, *_top_candidates(parsed_candidates.get("pattern", []), limit=_SURFACE_TOP_K)]
    detail_options = [None, *_top_candidates(parsed_candidates.get("detail", []), limit=_SURFACE_TOP_K)]
    for pattern in pattern_options:
        print_scale_options = [None] if pattern is None else [None, *_top_candidates(parsed_candidates.get("print_scale", []), limit=_SURFACE_TOP_K)]
        for print_scale in print_scale_options:
            for detail in detail_options:
                current = _selected_surface(pattern, print_scale, detail)
                evaluation = evaluate_selection_compatibility(current, rules)
                if evaluation.hard_conflicts:
                    continue
                rank = _selection_rank(current, evaluation)
                if rank > best_rank:
                    best_selected, best_evaluation, best_rank = current, evaluation, rank
    return best_selected, best_evaluation
```

- [ ] **Step 4: 重跑组合器测试**

Run: `python -m unittest tests.test_composition_engine -v`

Expected:
- `PASS`
- `selected_elements` 包含新 slot
- `print_scale` 仅在有 `pattern` 时出现
- `bodycon + drop waist` 被替代或省略

- [ ] **Step 5: 提交组合器改动**

```bash
git add temu_y2_women/composition_engine.py tests/test_composition_engine.py
git commit -m "feat(composition): select objective dress slots"
```

### Task 3: 扩展 prompt bundle，让新 slot 真正进入成图语义

**Files:**
- Modify: `temu_y2_women/prompt_renderer.py`
- Modify: `tests/test_prompt_renderer.py`

- [ ] **Step 1: 先写 prompt 失败测试**

```python
def test_render_mode_a_prompt_includes_objective_slots(self) -> None:
    from temu_y2_women.prompt_renderer import render_prompt_bundle

    bundle = render_prompt_bundle(
        request=_request(mode="A"),
        concept=_concept(),
        selected_strategies=(_strategy(),),
        warnings=(),
    )

    prompt = bundle["prompt"]
    self.assertIn("mini length", prompt)
    self.assertIn("drop waist", prompt)
    self.assertIn("white color story", prompt)
    self.assertIn("micro print scale", prompt)
    self.assertIn("sheer overlay effect", prompt)

    detail_prompts = {item["prompt_id"]: item["prompt"] for item in bundle["detail_prompts"]}
    self.assertIn("waistline placement", detail_prompts["construction_closeup"])
    self.assertIn("micro print scale", detail_prompts["fabric_print_closeup"])
    self.assertIn("mini proportion", detail_prompts["hem_and_drape_closeup"])
```

- [ ] **Step 2: 跑聚焦 prompt 测试，确认当前失败**

Run: `python -m unittest tests.test_prompt_renderer -v`

Expected:
- `FAIL`
- prompt 里缺少新增 slot 语义

- [ ] **Step 3: 实现 prompt 渲染扩展**

```python
def _element_phrase(slot: str, value: str) -> str:
    if slot == "silhouette":
        return f"{value} silhouette"
    if slot == "fabric":
        return f"{value} fabric"
    if slot == "dress_length":
        return f"{value} length"
    if slot == "color_family":
        return f"{value} color story"
    if slot == "print_scale":
        return f"{value} scale"
    if slot == "opacity_level" and value == "sheer":
        return "sheer overlay effect"
    return value
```

```python
def _construction_prompt(concept: ComposedConcept) -> str:
    neckline = concept.selected_elements["neckline"].value
    waistline = concept.selected_elements.get("waistline", concept.selected_elements["silhouette"]).value
    detail = concept.selected_elements.get("detail", concept.selected_elements["fabric"]).value
    return (
        f"close-up ecommerce detail image of the {neckline}, {detail}, and waistline placement; "
        f"clearly show {waistline}, seam lines, neckline edge finish, and bodice construction; "
        "neutral studio background; no hands, no accessories, no text"
    )
```

```python
def _fabric_prompt(concept: ComposedConcept) -> str:
    fabric = concept.selected_elements["fabric"].value
    pattern = concept.selected_elements.get("pattern", ComposedElement("", "solid color")).value
    print_scale = concept.selected_elements.get("print_scale", ComposedElement("", "commercial print")).value
    opacity = concept.selected_elements.get("opacity_level", ComposedElement("", "opaque")).value
    return (
        f"macro fabric detail image of {fabric} with {pattern} and {print_scale} scale; "
        f"clearly show {opacity} behavior, print scale, weave texture, and color accuracy; "
        "soft studio lighting; no blur, no props, no text"
    )
```

- [ ] **Step 4: 重跑 prompt 测试**

Run: `python -m unittest tests.test_prompt_renderer -v`

Expected:
- `PASS`
- hero / detail prompts 都显式携带新 slot 语义

- [ ] **Step 5: 提交 prompt 扩展**

```bash
git add temu_y2_women/prompt_renderer.py tests/test_prompt_renderer.py
git commit -m "feat(prompt): render objective dress slots"
```

### Task 4: 扩 factory spec builder，把新增 slot 写进生产草案

**Files:**
- Modify: `temu_y2_women/factory_spec_builder.py`
- Modify: `tests/test_factory_spec_builder.py`

- [ ] **Step 1: 先写 factory spec 失败测试**

```python
def test_build_factory_spec_carries_objective_slots_into_known_and_review_cues(self) -> None:
    from temu_y2_women.factory_spec_builder import build_factory_spec

    request, concept, selected_strategies = _build_success_inputs(
        "success-summer-vacation-mode-a.json"
    )
    factory_spec = build_factory_spec(
        request=request,
        concept=concept,
        selected_strategies=selected_strategies,
    )

    selected = factory_spec["known"]["selected_elements"]
    self.assertEqual(selected["dress_length"]["value"], "mini")
    self.assertEqual(selected["waistline"]["value"], "drop waist")
    self.assertEqual(selected["color_family"]["value"], "white")
    self.assertEqual(selected["print_scale"]["value"], "micro print")
    self.assertEqual(selected["opacity_level"]["value"], "sheer")

    inferred = factory_spec["inferred"]
    self.assertIn("fit cue: confirm drop-waist placement does not collapse the skirt balance", inferred["fit_review_cues"])
    self.assertIn("visible check: confirm micro print scale stays readable without muddying the fabric surface", inferred["visible_construction_checks"])
    self.assertIn("commercial cue: keep white color direction and sheer balance commercially readable in first-glance imagery", inferred["commercial_review_cues"])
```

- [ ] **Step 2: 跑聚焦 factory spec 测试，确认当前失败**

Run: `python -m unittest tests.test_factory_spec_builder -v`

Expected:
- `FAIL`
- `known.selected_elements` 缺少新增 slot
- review cues 不包含长度 / 腰线 / print scale / opacity 信息

- [ ] **Step 3: 实现 factory spec 扩展**

```python
def _fit_review_cues(
    request: NormalizedRequest,
    concept: ComposedConcept,
) -> list[str]:
    cues = []
    if _selected_value(concept, "waistline") == "drop waist":
        cues.append("fit cue: confirm drop-waist placement does not collapse the skirt balance")
    if _selected_value(concept, "dress_length") == "mini":
        cues.append("fit cue: confirm mini length still feels secure and commercially wearable in motion")
    if "bodycon" in request.avoid_tags:
        cues.append("fit cue: protect non-bodycon ease through bust, waist, and skirt sweep")
    return cues or ["fit cue: confirm the sample stays easy to wear for the intended market"]
```

```python
def _commercial_review_cues(
    request: NormalizedRequest,
    concept: ComposedConcept,
    selected_strategies: tuple[SelectedStrategy, ...],
) -> list[str]:
    cues = []
    if _selected_value(concept, "color_family") == "white" and _selected_value(concept, "opacity_level") == "sheer":
        cues.append("commercial cue: keep white color direction and sheer balance commercially readable in first-glance imagery")
    if _selected_value(concept, "print_scale") == "micro print":
        cues.append("commercial cue: keep micro print scale crisp enough to read without visual noise")
    if selected_strategies:
        cues.append(f"commercial cue: seasonal review should stay anchored to {selected_strategies[0].reason}")
    return cues
```

```python
def _visible_construction_checks(concept: ComposedConcept) -> list[str]:
    checks = []
    if _selected_value(concept, "waistline") == "drop waist":
        checks.append("visible check: confirm drop-waist seam reads level and balanced across the full body")
    if _selected_value(concept, "print_scale") == "micro print":
        checks.append("visible check: confirm micro print scale stays readable without muddying the fabric surface")
    if _selected_value(concept, "opacity_level") == "sheer":
        checks.append("visible check: confirm sheer behavior stays intentional rather than accidentally transparent")
    return checks
```

- [ ] **Step 4: 重跑 factory spec 测试**

Run: `python -m unittest tests.test_factory_spec_builder -v`

Expected:
- `PASS`
- 新 slot 进入 `known` 与 `inferred`

- [ ] **Step 5: 提交 factory spec 改动**

```bash
git add temu_y2_women/factory_spec_builder.py tests/test_factory_spec_builder.py
git commit -m "feat(factory-spec): reflect objective dress slots"
```

### Task 5: 回归验证与交付收口

**Files:**
- Modify: `temu_y2_women/composition_engine.py`（仅当验证暴露边角问题）
- Modify: `temu_y2_women/prompt_renderer.py`（仅当验证暴露边角问题）
- Modify: `temu_y2_women/factory_spec_builder.py`（仅当验证暴露边角问题）
- Modify: `tests/test_evidence_repository.py`
- Modify: `tests/test_composition_engine.py`
- Modify: `tests/test_prompt_renderer.py`
- Modify: `tests/test_factory_spec_builder.py`

- [ ] **Step 1: 跑本 change 相关回归**

Run:

```bash
python -m unittest tests.test_evidence_repository tests.test_composition_engine tests.test_prompt_renderer tests.test_factory_spec_builder -v
python -m py_compile temu_y2_women/evidence_repository.py temu_y2_women/composition_engine.py temu_y2_women/prompt_renderer.py temu_y2_women/factory_spec_builder.py tests/test_evidence_repository.py tests/test_composition_engine.py tests/test_prompt_renderer.py tests/test_factory_spec_builder.py
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- 所有聚焦单测通过
- `py_compile` 无输出
- 函数长度校验 `OK`

- [ ] **Step 2: 做一个概念+prompt 路径的代表性验证**

Run:

```bash
python - <<'PY'
from pathlib import Path
from temu_y2_women.orchestrator import generate_dress_concept

result = generate_dress_concept(
    request_path=Path("tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json")
)
print(sorted(result["composed_concept"]["selected_elements"].keys()))
print(result["prompt_bundle"]["prompt"])
PY
```

Expected:
- `selected_elements` 至少包含 `dress_length`、`waistline`、`color_family`
- prompt 文本中出现新增 slot 语义，而不是只剩旧的 `silhouette/fabric/pattern`

- [ ] **Step 3: 若验证暴露边角问题，只做最小修复**

```python
def _selected_surface(
    pattern: CandidateElement | None,
    print_scale: CandidateElement | None,
    detail: CandidateElement | None,
) -> dict[str, CandidateElement]:
    selected: dict[str, CandidateElement] = {}
    if pattern is not None:
        selected["pattern"] = pattern
    if pattern is not None and print_scale is not None:
        selected["print_scale"] = print_scale
    if detail is not None:
        selected["detail"] = detail
    return selected
```

- [ ] **Step 4: 最终整理提交**

```bash
git status --short
git log --oneline --decorate -5
```

Expected:
- 只包含 objective slot baseline / composition / prompt / factory spec 相关文件
- 提交粒度清晰，可直接作为 Change A 推 PR

- [ ] **Step 5: 推送分支**

```bash
git push -u origin codex/objective-slot-baseline
```

Expected:
- 远端分支创建成功
- 后续用 `git-pr-ship` 创建 PR，不直接合并到 `main`
