# Image Gateway Smoke Harness Implementation Plan

> Completion status: implemented on `main` and verified with focused smoke/provider tests, smoke module `py_compile`, function-length guard on `temu_y2_women tests`, and forbidden-pattern guard on 2026-05-01.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 固化 `gpt-image-2` 网关连通性探测，提供可重复执行的本地 smoke CLI，并输出结构化 JSON 诊断报告。

**Architecture:** 独立 CLI 负责参数与配置解析，smoke orchestration 模块负责定义和执行 5 个默认检查，原始 HTTP 模块负责 JSON/multipart 请求与 timeout/error body 捕获。整个实现不接入真实联网单测，也不改变现有 render workflow。

**Tech Stack:** Python 3 标准库、`urllib.request`、`json`、`unittest`、现有 `image_provider_config.py` 配置解析。

---

## File Map

- Create: `temu_y2_women/image_gateway_smoke_http.py`
- Create: `temu_y2_women/image_gateway_smoke.py`
- Create: `temu_y2_women/image_gateway_smoke_cli.py`
- Create: `tests/test_image_gateway_smoke.py`
- Create: `tests/test_image_gateway_smoke_cli.py`
- Create: `docs/superpowers/specs/2026-04-29-image-gateway-smoke-harness-design.md`
- Create: `docs/superpowers/plans/2026-04-29-image-gateway-smoke-harness.md`

### Task 1: 写 smoke 编排测试

**Files:**
- Create: `tests/test_image_gateway_smoke.py`

- [x] 写默认 5 检查报告结构测试
- [x] 写 `--check` 过滤测试
- [x] 写 timeout / 502 / 503 结构化映射测试
- [x] 运行 `python -m unittest tests.test_image_gateway_smoke -v`，确认先失败

### Task 2: 实现 HTTP 层与 smoke orchestration

**Files:**
- Create: `temu_y2_women/image_gateway_smoke_http.py`
- Create: `temu_y2_women/image_gateway_smoke.py`

- [x] 实现原始 JSON / multipart 请求能力
- [x] 实现 1x1 PNG 内置参考图
- [x] 实现默认 5 检查与 JSON 报告聚合
- [x] 重新运行 `python -m unittest tests.test_image_gateway_smoke -v`

### Task 3: 写 CLI 测试并实现 CLI

**Files:**
- Create: `tests/test_image_gateway_smoke_cli.py`
- Create: `temu_y2_women/image_gateway_smoke_cli.py`

- [x] 写 CLI 参数转发与配置解析测试
- [x] 写配置错误路径测试
- [x] 运行 `python -m unittest tests.test_image_gateway_smoke_cli -v`，确认先失败
- [x] 实现 `run` 子命令、stdout JSON 输出、返回码逻辑
- [x] 重新运行 `python -m unittest tests.test_image_gateway_smoke_cli -v`

### Task 4: 做回归验证并准备提交

**Files:**
- Verify only

- [x] 运行 `python -m unittest tests.test_image_gateway_smoke tests.test_image_gateway_smoke_cli tests.test_image_provider_config tests.test_image_generation_openai -v`
- [x] 运行 `python -m py_compile temu_y2_women\\image_gateway_smoke_http.py temu_y2_women\\image_gateway_smoke.py temu_y2_women\\image_gateway_smoke_cli.py`
- [x] 运行 `python C:\\Users\\lxy\\.codex\\rules\\hooks\\validate_python_function_length.py temu_y2_women tests`
- [x] 运行 `python C:\\Users\\lxy\\.codex\\rules\\hooks\\validate_forbidden_patterns.py .`
- [x] 检查 `git diff --stat`
- [x] 提交、推送、创建 PR
