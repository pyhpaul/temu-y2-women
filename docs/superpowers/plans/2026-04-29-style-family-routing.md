# Style Family Routing Implementation Plan

> Completion status: implementation tasks 1-7 are on `main` and verified with focused style-family suites, style modules `py_compile`, function-length guard on `temu_y2_women tests`, and forbidden-pattern guard on 2026-05-01. Task 8 remains pending because it requires local image generation under `tmp/style-family-routing/`.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在现有女装概念生成链路中加入 style family routing，让系统能输出 4 条明显不同的风格族群，而不是同一母版上的局部元素变化。

**Architecture:** 新增独立的 style family config + selector 层，请求先确定显式或自动 family，再让 candidate retrieval 施加 hard filter / soft boost，并让 prompt renderer 使用 family-specific 视觉外壳。strategy template 继续保留原职责，不与 style family 合并。

**Tech Stack:** Python 3、JSON runtime config、现有 `unittest` 体系、现有 concept generation / prompt rendering / image generation CLI、真实 `gpt-image-2` anchor generate 验证。

---

## File Map

- Create: `data/mvp/dress/style_families.json`
- Create: `temu_y2_women/style_family_repository.py`
- Create: `temu_y2_women/style_family_selector.py`
- Modify: `data/mvp/dress/elements.json`
- Modify: `data/mvp/dress/evidence_taxonomy.json`
- Modify: `temu_y2_women/models.py`
- Modify: `temu_y2_women/request_normalizer.py`
- Modify: `temu_y2_women/evidence_repository.py`
- Modify: `temu_y2_women/orchestrator.py`
- Modify: `temu_y2_women/prompt_renderer.py`
- Modify: `temu_y2_women/result_packager.py`
- Modify: `temu_y2_women/factory_spec_builder.py`
- Create: `tests/test_style_family_repository.py`
- Create: `tests/test_style_family_selector.py`
- Modify: `tests/test_request_normalizer.py`
- Modify: `tests/test_evidence_repository.py`
- Modify: `tests/test_prompt_renderer.py`
- Modify: `tests/test_factory_spec_builder.py`
- Modify: `tests/test_orchestrator.py`
- Create: `tmp/style-family-routing/requests/*.json`（人工验证输入，不进 git）

### Task 1: 建立 style family config contract 与 selector

**Files:**
- Create: `data/mvp/dress/style_families.json`
- Create: `temu_y2_women/style_family_repository.py`
- Create: `temu_y2_women/style_family_selector.py`
- Create: `tests/test_style_family_repository.py`
- Create: `tests/test_style_family_selector.py`

- [x] 先写 loader/selector 失败测试，固定 4 个 family 的 config shape
- [x] 运行 `python -m unittest tests.test_style_family_repository tests.test_style_family_selector -v`，确认先失败
- [x] 实现 config loader、active value 校验、显式选择和自动 fallback heuristic
- [x] 重新运行上述测试直到通过

### Task 2: 扩请求结构与成功结果 contract

**Files:**
- Modify: `temu_y2_women/models.py`
- Modify: `temu_y2_women/request_normalizer.py`
- Modify: `temu_y2_women/result_packager.py`
- Modify: `tests/test_request_normalizer.py`
- Modify: `tests/test_orchestrator.py`

- [x] 先写失败测试，固定 `style_family` 为 optional request field
- [x] 覆盖 unknown family / empty string / explicit family success 路径
- [x] 修改 dataclass 与 request normalize
- [x] 在 success result 中输出 `selected_style_family`
- [x] 跑 `python -m unittest tests.test_request_normalizer tests.test_orchestrator -v`

### Task 3: 扩元素库与 taxonomy，支撑 4 条 family

**Files:**
- Modify: `data/mvp/dress/elements.json`
- Modify: `data/mvp/dress/evidence_taxonomy.json`
- Modify: `tests/test_evidence_repository.py`

- [x] 先补足 family 所需新 tags / value
- [x] 新增能拉开差异的 fabric / neckline / sleeve / color / detail / length 元素
- [x] 确保新 active values 与 taxonomy 完全对齐
- [x] 跑 `python -m unittest tests.test_evidence_repository -v`

### Task 4: 将 style family 接入 candidate retrieval

**Files:**
- Modify: `temu_y2_women/evidence_repository.py`
- Modify: `tests/test_evidence_repository.py`
- Modify: `tests/test_orchestrator.py`

- [x] 先写失败测试，覆盖 hard filter / blocked value / soft boost / explicit conflict fail-closed
- [x] 运行对应测试，确认当前失败
- [x] 实现 family-aware candidate filtering/scoring
- [x] 保证 strategy 与 style family 可以叠加
- [x] 重新运行相关测试直到通过

### Task 5: 将 style family 接入 orchestrator 与 factory spec

**Files:**
- Modify: `temu_y2_women/orchestrator.py`
- Modify: `temu_y2_women/factory_spec_builder.py`
- Modify: `tests/test_factory_spec_builder.py`
- Modify: `tests/test_orchestrator.py`

- [x] 先写失败测试，固定 `selected_style_family_id` 出现在 result / factory spec
- [x] 实现 orchestrator 的 family 加载与传递
- [x] 实现 factory spec 的 known/inferred family 补充
- [x] 运行 `python -m unittest tests.test_factory_spec_builder tests.test_orchestrator -v`

### Task 6: 让 prompt shell 真正分化

**Files:**
- Modify: `temu_y2_women/prompt_renderer.py`
- Modify: `tests/test_prompt_renderer.py`

- [x] 先写失败测试，固定 4 个 family 的主图 prompt shell 差异
- [x] 要求至少在 subject / scene / lighting / styling / avoid 项上可见分化
- [x] 实现 family-specific prompt shell
- [x] 运行 `python -m unittest tests.test_prompt_renderer -v`

### Task 7: 做端到端回归验证

**Files:**
- Verify only

- [x] 运行 `python -m unittest -v`
- [x] 运行 `python -m py_compile temu_y2_women\\style_family_repository.py temu_y2_women\\style_family_selector.py temu_y2_women\\models.py temu_y2_women\\request_normalizer.py temu_y2_women\\evidence_repository.py temu_y2_women\\orchestrator.py temu_y2_women\\prompt_renderer.py temu_y2_women\\result_packager.py temu_y2_women\\factory_spec_builder.py`
- [x] 运行 `python C:\\Users\\lxy\\.codex\\rules\\hooks\\validate_python_function_length.py temu_y2_women tests`
- [x] 运行 `python C:\\Users\\lxy\\.codex\\rules\\hooks\\validate_forbidden_patterns.py .`

### Task 8: 生成 4 张 anchor 主图做人工验收

**Files:**
- Create local only: `tmp/style-family-routing/`

- [ ] 准备 4 个请求：
  - `vacation-romantic`
  - `clean-minimal`
  - `city-polished`
  - `party-fitted`
- [ ] 只跑 `hero_front generate`
- [ ] 落盘 prompt / concept / image / manifest
- [ ] 验收“只看图是否一眼能区分”

### Task 9: 提交、推送、创建 PR

**Files:**
- Verify only

- [ ] 检查 `git diff --stat`
- [ ] 精确 `git add` 本次改动
- [ ] 提交 Why / What / Test 格式 commit
- [ ] 推送分支并自动创建 PR
