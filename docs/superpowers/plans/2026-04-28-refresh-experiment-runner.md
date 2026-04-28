# Refresh Experiment Runner Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增一条隔离式 refresh experiment 流程，对一组 request 先跑 baseline，再在实验副本 evidence 上 apply reviewed promotion，并输出 per-request compare 与 aggregate report。

**Architecture:** 复用 `refresh_run_promotion.py` 负责从 refresh run 生成/应用 promotion，复用 `orchestrator.generate_dress_concept()` 负责 baseline 与 rerun。新增 `refresh_experiment_runner.py` 负责 request set、实验工作区、批量执行、compare/aggregate 报告；新增薄 CLI `refresh_experiment_runner_cli.py` 负责 `prepare` / `apply` 参数分发。

**Tech Stack:** Python 3、`unittest`、现有 `GenerationError` 错误模型、现有 `EvidencePaths` 证据路径覆盖机制。

---

## File map

- Create: `temu_y2_women/refresh_experiment_runner.py`
- Create: `temu_y2_women/refresh_experiment_runner_cli.py`
- Create: `tests/test_refresh_experiment_runner.py`
- Create: `tests/test_refresh_experiment_runner_cli.py`
- Modify: `docs/superpowers/specs/2026-04-28-refresh-experiment-runner-design.md`（仅当实现后需要补充落地偏差）

### Task 1: 建 request set / workspace 基础设施

**Files:**
- Create: `temu_y2_women/refresh_experiment_runner.py`
- Create: `tests/test_refresh_experiment_runner.py`

- [ ] **Step 1: 先写 request set 校验的失败测试**

```python
class RefreshExperimentPrepareValidationTest(unittest.TestCase):
    def test_prepare_rejects_duplicate_request_ids(self) -> None:
        from temu_y2_women.refresh_experiment_runner import prepare_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            request_set_path = temp_root / "request-set.json"
            _write_json(
                request_set_path,
                {
                    "schema_version": "refresh-experiment-request-set-v1",
                    "category": "dress",
                    "requests": [
                        {"request_id": "dup", "request_path": str(_REQUEST_FIXTURE_PATH)},
                        {"request_id": "dup", "request_path": str(_SUMMER_REQUEST_FIXTURE_PATH)},
                    ],
                },
            )

            result = prepare_refresh_experiment(
                run_dir=_seed_refresh_run(temp_root, scenario="create"),
                request_set_path=request_set_path,
                experiment_root=temp_root / "experiments",
                source_paths=_seed_experiment_source_paths(temp_root),
            )

        self.assertEqual(result["error"]["code"], "INVALID_REFRESH_EXPERIMENT_INPUT")
        self.assertEqual(result["error"]["details"]["field"], "request_id")
```

- [ ] **Step 2: 跑单测确认当前失败**

Run: `python -m unittest tests.test_refresh_experiment_runner.RefreshExperimentPrepareValidationTest.test_prepare_rejects_duplicate_request_ids -v`  
Expected: FAIL，原因是 `prepare_refresh_experiment` 尚不存在。

- [ ] **Step 3: 实现 request set / workspace 基础 helpers**

```python
@dataclass(frozen=True, slots=True)
class RefreshExperimentSourcePaths:
    evidence_paths: EvidencePaths


def _load_request_set_manifest(path: Path) -> dict[str, Any]:
    payload = _load_json_object(path, code="INVALID_REFRESH_EXPERIMENT_INPUT")
    if payload.get("schema_version") != "refresh-experiment-request-set-v1":
        raise _experiment_input_error(path, "schema_version", "unsupported request set schema version")
    if payload.get("category") != "dress":
        raise _experiment_input_error(path, "category", "refresh experiment currently supports dress only")
    requests = payload.get("requests")
    if not isinstance(requests, list) or not requests:
        raise _experiment_input_error(path, "requests", "request set must contain at least one request")
    _validate_request_entries(path, requests)
    return payload


def _workspace_paths(workspace_root: Path) -> dict[str, Any]:
    evidence_root = workspace_root / "data" / "mvp" / "dress"
    return {
        "evidence_paths": EvidencePaths(
            elements_path=evidence_root / "elements.json",
            strategies_path=evidence_root / "strategy_templates.json",
            taxonomy_path=evidence_root / "evidence_taxonomy.json",
        ),
        "baseline_dir": workspace_root / "baseline",
        "post_apply_dir": workspace_root / "post_apply",
        "compare_dir": workspace_root / "compare",
    }
```

- [ ] **Step 4: 重跑校验测试**

Run: `python -m unittest tests.test_refresh_experiment_runner.RefreshExperimentPrepareValidationTest.test_prepare_rejects_duplicate_request_ids -v`  
Expected: PASS

- [ ] **Step 5: 提交基础设施骨架**

```bash
git add tests/test_refresh_experiment_runner.py temu_y2_women/refresh_experiment_runner.py
git commit -m "test: add refresh experiment request set validation"
```

### Task 2: 实现 prepare 流程与 baseline 批量落盘

**Files:**
- Modify: `temu_y2_women/refresh_experiment_runner.py`
- Modify: `tests/test_refresh_experiment_runner.py`

- [ ] **Step 1: 写 prepare 成功链路测试**

```python
class RefreshExperimentPrepareTest(unittest.TestCase):
    def test_prepare_creates_workspace_manifest_review_and_baselines(self) -> None:
        from unittest.mock import patch

        from temu_y2_women.refresh_experiment_runner import prepare_refresh_experiment

        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            request_set_path = _write_request_set(
                temp_root,
                requests=[
                    ("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH),
                    ("transitional-a", _REQUEST_FIXTURE_PATH),
                ],
            )
            with patch(
                "temu_y2_women.refresh_experiment_runner._next_experiment_id",
                return_value="exp-refresh-001",
            ), patch(
                "temu_y2_women.refresh_experiment_runner._current_timestamp",
                return_value="2026-04-28T12:00:00Z",
            ):
                result = prepare_refresh_experiment(
                    run_dir=_seed_refresh_run(temp_root, scenario="create"),
                    request_set_path=request_set_path,
                    experiment_root=temp_root / "experiments",
                    workspace_name="batch-a",
                    source_paths=_seed_experiment_source_paths(temp_root),
                )

        manifest = _read_json(Path(result["manifest_path"]))
        self.assertEqual(result["experiment_id"], "exp-refresh-001")
        self.assertTrue((temp_root / "experiments" / "batch-a" / "promotion_review.json").exists())
        self.assertTrue((temp_root / "experiments" / "batch-a" / "baseline" / "summer-vacation-a.json").exists())
        self.assertEqual(manifest["request_count"], 2)
```

- [ ] **Step 2: 跑 prepare 测试确认失败**

Run: `python -m unittest tests.test_refresh_experiment_runner.RefreshExperimentPrepareTest.test_prepare_creates_workspace_manifest_review_and_baselines -v`  
Expected: FAIL，原因是 prepare 尚未输出 manifest/review/baseline 工件。

- [ ] **Step 3: 实现 prepare_refresh_experiment 主流程**

```python
def prepare_refresh_experiment(
    run_dir: Path,
    request_set_path: Path,
    experiment_root: Path,
    workspace_name: str | None = None,
    source_paths: RefreshExperimentSourcePaths | None = None,
) -> dict[str, Any]:
    try:
        source = source_paths or RefreshExperimentSourcePaths(evidence_paths=EvidencePaths.defaults())
        request_set = _load_request_set_manifest(request_set_path)
        experiment_id = _next_experiment_id()
        workspace_root = _resolve_workspace_root(experiment_root, workspace_name, experiment_id)
        paths = _workspace_paths(workspace_root)
        _copy_workspace_inputs(source, paths)
        promotion_review = prepare_dress_promotion_from_refresh_run(
            run_dir=run_dir,
            active_elements_path=paths["evidence_paths"].elements_path,
            active_strategies_path=paths["evidence_paths"].strategies_path,
            output_path=workspace_root / "promotion_review.json",
            taxonomy_path=paths["evidence_paths"].taxonomy_path,
        )
        _raise_on_error_payload(promotion_review)
        baseline_index = _write_baseline_batch(request_set, paths["baseline_dir"], paths["evidence_paths"])
        manifest_path = workspace_root / "experiment_manifest.json"
        _write_json(manifest_path, _manifest_payload(...))
        return _prepare_result(...)
    except GenerationError as error:
        return error.to_dict()
```

- [ ] **Step 4: 运行 prepare 相关测试**

Run: `python -m unittest tests.test_refresh_experiment_runner.RefreshExperimentPrepareValidationTest tests.test_refresh_experiment_runner.RefreshExperimentPrepareTest -v`  
Expected: PASS

- [ ] **Step 5: 提交 prepare 流程**

```bash
git add tests/test_refresh_experiment_runner.py temu_y2_women/refresh_experiment_runner.py
git commit -m "feat: add refresh experiment prepare flow"
```

### Task 3: 实现 apply 流程、per-request compare 与 aggregate report

**Files:**
- Modify: `temu_y2_women/refresh_experiment_runner.py`
- Modify: `tests/test_refresh_experiment_runner.py`

- [ ] **Step 1: 写 apply 成功链路与 fail-closed 测试**

```python
class RefreshExperimentApplyTest(unittest.TestCase):
    def test_apply_writes_post_apply_compare_and_aggregate_reports(self) -> None:
        prepared = _prepare_refresh_experiment(
            scenario="create",
            request_entries=[
                ("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH),
                ("transitional-a", _REQUEST_FIXTURE_PATH),
            ],
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
        compare = _read_json(Path(result["compare_dir"]) / "summer-vacation-a.json")
        self.assertEqual(report["request_count"], 2)
        self.assertIn(compare["change_type"], {"selection_changed", "retrieval_changed_only", "score_changed_only"})
        self.assertIn("accepted_evidence_summary", report)

    def test_apply_fail_closed_does_not_leave_partial_compare_outputs(self) -> None:
        prepared = _prepare_refresh_experiment(
            scenario="create",
            request_entries=[("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)],
        )
        review_path = Path(prepared["promotion_review_path"])
        review_path.write_text("{", encoding="utf-8")

        result = apply_refresh_experiment(
            manifest_path=Path(prepared["manifest_path"]),
            reviewed_path=review_path,
        )

        self.assertEqual(result["error"]["code"], "INVALID_PROMOTION_REVIEW")
        self.assertFalse((Path(prepared["workspace_root"]) / "compare").exists())
```

- [ ] **Step 2: 跑 apply 测试确认失败**

Run: `python -m unittest tests.test_refresh_experiment_runner.RefreshExperimentApplyTest -v`  
Expected: FAIL，原因是 apply/report/compare 尚未实现。

- [ ] **Step 3: 实现 apply_refresh_experiment、compare helpers、aggregate helpers**

```python
def apply_refresh_experiment(manifest_path: Path, reviewed_path: Path | None = None) -> dict[str, Any]:
    try:
        manifest = _load_json_object(manifest_path, code="INVALID_REFRESH_EXPERIMENT_INPUT")
        workspace_root = Path(manifest["workspace_root"])
        paths = _manifest_workspace_paths(manifest)
        resolved_reviewed = reviewed_path or Path(manifest["promotion_review_path"])
        promotion_report_path = workspace_root / "promotion_report.json"
        apply_report = apply_reviewed_dress_promotion_from_refresh_run(
            run_dir=Path(manifest["run_dir"]),
            active_elements_path=paths["evidence_paths"].elements_path,
            active_strategies_path=paths["evidence_paths"].strategies_path,
            reviewed_path=resolved_reviewed,
            report_path=promotion_report_path,
            taxonomy_path=paths["evidence_paths"].taxonomy_path,
        )
        _raise_on_error_payload(apply_report)
        compare_index = _write_post_apply_batch_and_compare(manifest, paths, resolved_reviewed, apply_report)
        report_path = workspace_root / "experiment_report.json"
        _write_json(report_path, _build_experiment_report(manifest, compare_index, resolved_reviewed, apply_report))
        return _apply_result(...)
    except GenerationError as error:
        return error.to_dict()
```

```python
def _classify_change(selected_changes: dict[str, Any], retrieval_changes: list[dict[str, Any]], score_delta: float, factory_spec_changes: dict[str, Any]) -> str:
    if selected_changes:
        return "selection_changed"
    if retrieval_changes:
        return "retrieval_changed_only"
    if score_delta != 0:
        return "score_changed_only"
    if factory_spec_changes["changed"]:
        return "factory_spec_changed_only"
    return "no_observable_change"
```

- [ ] **Step 4: 运行 runner 全量单测**

Run: `python -m unittest tests.test_refresh_experiment_runner -v`  
Expected: PASS

- [ ] **Step 5: 提交 apply 与 compare/report**

```bash
git add tests/test_refresh_experiment_runner.py temu_y2_women/refresh_experiment_runner.py
git commit -m "feat: add refresh experiment apply reporting"
```

### Task 4: 新增 CLI 与 module entrypoint 覆盖

**Files:**
- Create: `temu_y2_women/refresh_experiment_runner_cli.py`
- Create: `tests/test_refresh_experiment_runner_cli.py`

- [ ] **Step 1: 写 CLI prepare/apply 与 module entrypoint 测试**

```python
class RefreshExperimentCliTest(unittest.TestCase):
    def test_prepare_cli_prints_manifest_summary(self) -> None:
        from temu_y2_women.refresh_experiment_runner_cli import main

        stdout = io.StringIO()
        with TemporaryDirectory() as temp_dir, patch("sys.stdout", stdout):
            exit_code = main(
                [
                    "prepare",
                    "--run-dir",
                    str(_seed_refresh_run(Path(temp_dir), scenario="create")),
                    "--request-set",
                    str(_write_request_set(Path(temp_dir), requests=[("summer-vacation-a", _SUMMER_REQUEST_FIXTURE_PATH)])),
                    "--experiment-root",
                    str(Path(temp_dir) / "experiments"),
                ]
            )

        self.assertEqual(exit_code, 0)
        self.assertIn("manifest_path", json.loads(stdout.getvalue()))
```

- [ ] **Step 2: 跑 CLI 测试确认失败**

Run: `python -m unittest tests.test_refresh_experiment_runner_cli -v`  
Expected: FAIL，原因是 CLI 文件尚不存在。

- [ ] **Step 3: 实现薄 CLI 封装**

```python
def _run_command(args: argparse.Namespace) -> dict[str, object]:
    if args.command == "prepare":
        return prepare_refresh_experiment(
            run_dir=Path(args.run_dir),
            request_set_path=Path(args.request_set),
            experiment_root=Path(args.experiment_root),
            workspace_name=args.workspace_name,
        )
    return apply_refresh_experiment(
        manifest_path=Path(args.manifest),
        reviewed_path=_optional_path(args.reviewed),
    )
```

- [ ] **Step 4: 运行 CLI 与 module entrypoint 测试**

Run: `python -m unittest tests.test_refresh_experiment_runner_cli -v`  
Expected: PASS

- [ ] **Step 5: 提交 CLI**

```bash
git add tests/test_refresh_experiment_runner_cli.py temu_y2_women/refresh_experiment_runner_cli.py
git commit -m "feat: add refresh experiment runner cli"
```

### Task 5: 收尾验证与发版动作

**Files:**
- Modify: `temu_y2_women/refresh_experiment_runner.py`（仅当验证暴露边角问题）
- Modify: `temu_y2_women/refresh_experiment_runner_cli.py`（仅当验证暴露边角问题）
- Modify: `tests/test_refresh_experiment_runner.py`
- Modify: `tests/test_refresh_experiment_runner_cli.py`

- [ ] **Step 1: 跑本 change 相关验证**

Run:

```bash
python -m unittest tests.test_refresh_experiment_runner tests.test_refresh_experiment_runner_cli -v
python -m unittest tests.test_refresh_run_promotion tests.test_evidence_promotion_cli tests.test_evidence_promotion tests.test_feedback_experiment_runner -v
python -m py_compile temu_y2_women/refresh_experiment_runner.py temu_y2_women/refresh_experiment_runner_cli.py
python C:\Users\lxy\.codex\rules\hooks\validate_python_function_length.py .
```

Expected:
- 所有单测通过
- `py_compile` 无输出
- 函数长度校验通过

- [ ] **Step 2: 若验证失败，做最小修复并重复验证**

```python
# 只允许针对失败点做最小改动，例如：
def _factory_spec_summary(factory_spec: dict[str, Any]) -> dict[str, Any]:
    known = factory_spec.get("known", {})
    selected = known.get("selected_elements", {})
    return {
        "known_keys": sorted(known.keys()),
        "selected_element_slots": sorted(selected.keys()),
        "unresolved_count": len(factory_spec.get("unresolved", [])),
    }
```

- [ ] **Step 3: 合并本 change 的实现提交**

```bash
git status --short
git log --oneline --decorate -5
```

Expected:
- 只有 refresh experiment runner 相关文件有变更
- 最近提交可整理为一组清晰 feature commits

- [ ] **Step 4: 最终提交**

```bash
git add tests/test_refresh_experiment_runner.py tests/test_refresh_experiment_runner_cli.py temu_y2_women/refresh_experiment_runner.py temu_y2_women/refresh_experiment_runner_cli.py
git commit -m "feat: add refresh experiment runner"
```

- [ ] **Step 5: 推送并创建 PR**

```bash
git push -u origin codex/refresh-experiment-runner
```

Expected:
- 远端分支创建成功
- 后续由 `git-pr-ship` 创建 PR，避免直接推 `main`
