# Image Gateway Smoke Harness 设计稿

整理日期：2026-04-29

## 1. 目标

把今天手工完成的 `gpt-image-2` 网关探测，固化成一条可重复执行的本地 smoke CLI，专门回答三个问题：

1. 基础网关是否可达
2. anchor `generations` 路由是否可达
3. derived `edits` 路由是否可达

它的职责是输出结构化诊断结果，不是替代正式渲染链路，也不是引入任何 `edit -> generation` 降级。

## 2. 范围

### 2.1 包含

- 新增独立 CLI：`python -m temu_y2_women.image_gateway_smoke_cli run`
- 读取现有 OpenAI-compatible 配置来源：
  - CLI flags
  - 环境变量
  - 仓库 `.env`
  - `~/.codex/auth.json`
  - `~/.codex/config.toml`
- 固化 5 个默认检查：
  - `models`
  - `generate-anchor`
  - `generate-expansion`
  - `edit-anchor`
  - `edit-expansion`
- 输出结构化 JSON 报告
- 提供可选 `--check` 只跑指定检查

### 2.2 不包含

- 不改现有 `generate_and_render` / `image_generation` 工作流
- 不接入单元测试里的真实联网调用
- 不把 `images/generations` 当作 `images/edits` 的 fallback
- 不增加图片内容质量评估

## 3. 关键设计决定

### 3.1 使用独立 CLI，不挂到现有渲染 CLI

这是基础设施诊断，不是业务渲染动作。独立 CLI 可以避免：

- 污染既有参数语义
- 把“网关连通性问题”和“图片工作流问题”混在一起
- 将来调 smoke 时误触发业务产物落盘

### 3.2 使用原始 HTTP，而不是 OpenAI SDK

smoke 的重点是保留最原始的网关观测：

- HTTP code
- timeout
- 原始 error body
- route 维度成功/失败

SDK 会帮忙封装异常，但会损失当前排障最关心的原始响应细节，因此这里直接走标准库 HTTP。

### 3.3 默认做全量 5 检查，但支持手动裁剪

默认全量检查能保证每次重跑都覆盖：

- 基础鉴权
- anchor 路由
- expansion 路由
- generation 路由
- edit 路由

同时支持 `--check`，便于只复测某一条坏路由。

### 3.4 expansion key 缺失时回退 anchor key，但显式保留 route 标签

如果没有单独 expansion key，smoke 仍然可以执行 expansion 检查，便于最小化配置门槛。

但报告中 `credential_route` 仍然保留：

- `anchor`
- `expansion`

这样用户能区分“逻辑路由角色”和“实际密钥是否共用”。

### 3.5 派生图策略保持不变

本工具只做探测，不能改变项目级策略：

- `hero_front` 可以走 `generate`
- derived hero/detail 必须走 `edit`
- `edit` 不可用时直接报错
- 不允许自动退回 `generations`

## 4. 模块结构

新增 3 个模块：

- `temu_y2_women/image_gateway_smoke_http.py`
  - 原始 HTTP 请求与 multipart 构造
- `temu_y2_women/image_gateway_smoke.py`
  - smoke check 定义、执行编排、报告聚合
- `temu_y2_women/image_gateway_smoke_cli.py`
  - CLI 参数解析、配置解析、stdout JSON 输出

## 5. CLI 合同

命令：

```bash
python -m temu_y2_women.image_gateway_smoke_cli run
```

支持参数：

- `--check`
- `--model`，默认 `gpt-image-2`
- `--base-url`
- `--anchor-api-key`
- `--expansion-api-key`
- `--timeout-sec`

行为：

1. 解析 provider config
2. 执行指定或默认 smoke checks
3. 打印 JSON 报告到 stdout
4. 只要存在失败检查，CLI 返回码为 `1`

## 6. 报告结构

报告采用单一 schema：

```json
{
  "schema_version": "image-gateway-smoke-report-v1",
  "model": "gpt-image-2",
  "base_url": "https://www.aerorelay.one/v1",
  "timeout_sec": 90.0,
  "checks": [
    {
      "check_id": "edit-expansion",
      "route": "POST /v1/images/edits",
      "credential_route": "expansion",
      "status": "failed",
      "ok": false,
      "http_code": 502,
      "elapsed_seconds": 0.73,
      "error_type": "upstream_error",
      "response_excerpt": "{\"error\":...}"
    }
  ],
  "summary": {
    "total": 5,
    "passed": 1,
    "failed": 4
  }
}
```

约束：

- 不输出任何 API key
- 保留原始错误摘要
- 保留路由与 credential route 信息

## 7. 错误处理

### 7.1 配置错误

继续复用 `INVALID_IMAGE_PROVIDER_CONFIG`：

- anchor key 缺失
- `.env` / `auth.json` / `config.toml` 解析失败

这类错误直接返回结构化 error 对象，不进入 smoke 执行。

### 7.2 远端调用失败

远端失败不抛业务异常，而是固化到 check result：

- `http_code`
- `elapsed_seconds`
- `error_type`
- `response_excerpt`

典型类型：

- `timeout`
- `network_error`
- `upstream_error`
- `api_error`
- `http_error`

## 8. 测试策略

### 8.1 CLI 测试

覆盖：

- `.env` / `.codex` 配置解析
- CLI 显式值覆盖
- stdout JSON 输出
- 失败检查返回码为 `1`

### 8.2 smoke 编排测试

覆盖：

- 默认 5 检查顺序
- `--check` 过滤
- timeout / 502 / 503 映射到结构化报告
- summary 统计正确

### 8.3 HTTP 层测试

只做本地假 transport 测试：

- JSON POST
- multipart edit POST
- HTTPError body 提取
- timeout / network error 映射

不做真实联网单测。
