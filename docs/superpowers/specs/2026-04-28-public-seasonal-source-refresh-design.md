# Public Seasonal Source Refresh 设计稿

整理日期：2026-04-28

## 1. 目标

当前项目已经有一条本地可用的证据链：

```text
signal bundle
-> signal_ingestion
-> draft_elements / draft_strategy_hints
-> review / promotion
-> active evidence
```

这次 change 的目标，是把这条链路升级为最小可用的**公开信息自动扩元素库**流程：

```text
public seasonal / holiday themed source
-> raw source snapshot
-> canonical signals
-> signal bundle compatibility layer
-> signal_ingestion
-> staged draft evidence
-> review / promotion
```

完成后，系统可以从 1 个真实公开文本源中提取季节/节日相关 dress signals，生成可审阅的 staged drafts，但仍保持 active evidence 只通过 review-gated promotion 进入主链。

## 2. 范围

### 2.1 包含

1. 支持 1 个真实公开的季节/节日主题文本源
2. 引入 source registry + source adapter 边界
3. 引入 richer 的 `canonical-signals-v1` contract
4. 从 canonical signals 生成兼容现有 ingestion 的 `signal-bundle-v1` 输入
5. 将刷新产物写入独立 refresh 目录
6. 继续复用现有 `signal_ingestion`、review、promotion 流程
7. 支持手动触发，并保留日级调度入口

### 2.2 不包含

- 自动 promotion 到 active evidence
- 多 market
- 多 category
- 商品详情页 / 零售类目页抓取
- 真实价格抽取
- 跨 run 全局去重仓
- 多源冲突合并
- 基于 signals 的 runtime 动态加权

## 3. 关键设计决定

### 3.1 首源选择“季节/节日主题文本源”，不选纯节日日历

纯日历源只能稳定提供 `occasion` / `season` 上下文，不能稳定提供具体 dress element 词汇。  
如果第一版只接日历源，更多是在扩标签，不是在扩元素库。

因此第一版首源应是公开的主题文本源，例如：

- seasonal guide
- holiday style guide
- editorial trend article
- themed landing page with descriptive copy

这些页面更容易同时提供：

- season / occasion
- 服装结构词
- 材质 / 版型 / pattern / detail 词

### 3.2 在现有 `signal-bundle-v1` 前加一层 canonical contract

公开源会带来更多 provenance、excerpt、fallback 与 warning 信息，现有 `signal-bundle-v1` 无法完整承载。  
因此不让 adapter 直接产出旧 signal shape，而是引入中间层：

```text
raw source snapshot
-> canonical-signals-v1
-> signal-bundle-v1 compatibility layer
```

这保证：

- 现有 `signal_ingestion` 可继续无改动复用
- richer signal 信息可留给后续 rule derivation / review 使用
- 新增 source 时不需要反复修改 ingestion contract

### 3.3 公开源刷新不直接触碰 active evidence

refresh 只写 staged artifacts，不写：

- `data/mvp/dress/elements.json`
- `data/mvp/dress/strategy_templates.json`

active evidence 仍只能通过现有 review/apply workflow 进入主链，保持 fail-closed 与可审计性。

### 3.4 价格带采用“最小诚实 fallback”

主题文本源通常没有真实价格。  
现有 ingestion 又要求 `observed_price_band` 必填。

第一版做法：

- 当 source 无真实价格时，使用 source-level default price band
- 同时强制记录 `price_band_resolution = "source_default"`
- 在 refresh report 中记录 fallback 使用次数

第一版默认 price band 可固定为 `mid`，但不得伪装为真实观测值。

## 4. 架构

建议拆成 5 层：

### 4.1 Source registry

职责：

- 维护启用的公开 source 清单
- 声明 source 元数据与默认配置

每个 source 至少包含：

- `source_id`
- `source_type`
- `source_url`
- `target_market`
- `category`
- `fetch_mode`
- `default_price_band`
- `enabled`
- `adapter_version`

第一版 registry 只需要支持静态 JSON 配置。

### 4.2 Source adapter

职责：

- 读取单个 source
- 抽取可复用文本块与必要元数据
- 输出统一 `raw_source_snapshot`

adapter 不负责：

- 生成旧 signal bundle
- 直接生成 elements
- 直接做 review / promotion

这样可以把“源特定解析”与“平台内证据链”解耦。

### 4.3 Canonical signal builder

职责：

- 将 `raw_source_snapshot` 归一成 `canonical-signals-v1`
- 对 season / occasion / tags / price-band-resolution 做标准化
- 记录 extraction provenance 与 warnings

这是后续并行接入：

- staged element refresh
- signal-derived conflict candidates

的公共 contract。

### 4.4 Signal bundle compatibility layer

职责：

- 将 canonical signals 映射成现有 `signal-bundle-v1`
- 保持 `signal_ingestion` 无改动复用

规则：

- `signal_id = canonical_signal_id`
- 旧 ingestion 所需字段必须完整输出
- richer provenance 字段允许保留，但不能破坏旧链路

### 4.5 Staged draft extraction and promotion

职责：

- 调用现有 `signal_ingestion`
- 产出：
  - `normalized_signals.json`
  - `draft_elements.json`
  - `draft_strategy_hints.json`
  - `ingestion_report.json`
- 后续由人工 review / promotion 决定是否进入 active evidence

## 5. canonical-signals-v1 contract

每条 canonical signal 至少包含：

- `canonical_signal_id`
- `source_id`
- `source_type`
- `source_url`
- `captured_at`
- `fetched_at`
- `target_market`
- `category`
- `title`
- `summary`
- `evidence_excerpt`
- `observed_occasion_tags`
- `observed_season_tags`
- `manual_tags`
- `observed_price_band`
- `price_band_resolution`
- `status`
- `extraction_provenance`

字段语义：

- `canonical_signal_id`：稳定 id，建议由 `source_id + page_id + chunk_index` 组合生成
- `captured_at`：内容原始日期，未知时允许为空字符串，但必须在 report 中记录
- `fetched_at`：实际抓取时间
- `evidence_excerpt`：用于证明该 signal 成立的关键文本片段
- `price_band_resolution`：
  - `observed`
  - `source_default`
  - `rule_fallback`
- `status`：第一版固定为 `active`

`extraction_provenance` 至少记录：

- `source_section`
- `matched_keywords`
- `adapter_version`
- `warnings`
- `confidence`（若有）

## 6. signal-bundle-v1 compatibility

canonical signal 需要稳定映射到现有 ingestion 所需字段：

- `signal_id`
- `source_type`
- `source_url`
- `captured_at`
- `target_market`
- `category`
- `title`
- `summary`
- `observed_price_band`
- `observed_occasion_tags`
- `observed_season_tags`
- `manual_tags`
- `status`

映射规则：

- `signal_id = canonical_signal_id`
- `source_type` 使用 canonical 中的归一结果
- `title / summary / tags / season / occasion / price_band` 直接映射
- extra provenance 字段可附加，但当前 ingestion 不依赖它们

这层的目的是保持老链路稳定，而不是重新定义 ingestion。

## 7. 目录与产物

refresh run 使用独立目录：

```text
data/refresh/dress/<run_id>/
  source_registry_snapshot.json
  raw_sources/
    <source_id>.json
  canonical_signals.json
  signal_bundle.json
  normalized_signals.json
  draft_elements.json
  draft_strategy_hints.json
  ingestion_report.json
  refresh_report.json
```

### 7.1 source_registry_snapshot.json

记录本次 run 实际使用的 source 配置，保证复盘时不依赖外部 registry 当前态。

### 7.2 raw_sources/<source_id>.json

保存单源抓取与抽取结果：

- source metadata
- 原始文本块
- 抽取 section
- source 级 warnings / errors

### 7.3 canonical_signals.json

本次 run 的核心中间产物，是后续 element refresh 与 conflict-rule derivation 的统一信号层。

### 7.4 signal_bundle.json

给现有 `signal_ingestion` 复用的兼容输入。

### 7.5 refresh_report.json

总结 run 质量，至少包含：

- `run_id`
- `started_at`
- `completed_at`
- `source_summary`
- `canonical_signal_count`
- `signal_bundle_count`
- `fallback_price_band_count`
- `warnings`
- `errors`

## 8. 错误处理与 fail-closed

### 8.1 Source 级容错

单个 source 失败时：

- 不终止整个 run
- 在 report 中记录：
  - `source_id`
  - `stage`
  - `error_code`
  - `message`

适用阶段：

- fetch
- parse
- canonicalize

这样后续多源时不会因为单源异常导致整批不可用。

### 8.2 Run 级 fail-closed

以下情况要让本次 run 失败，不进入可推广语义：

1. source registry 非法
2. canonical signal contract 非法
3. compatibility bundle 无法稳定映射
4. 0 条有效 canonical signals
5. `signal_ingestion` 返回 error
6. 关键 staged artifact 写入失败

原则：

- 允许 source 局部失败
- 不允许 contract 模糊成功

## 9. 手动触发与日级刷新

第一版支持两种入口，但共用一个 runner：

1. 手动触发 CLI
2. 日级调度入口

调度系统本身不放进这次 change 的核心范围。  
外层可以用 Task Scheduler、cron 或 CI 调用同一 runner。

这样调度逻辑不会与 source parsing 或 evidence promotion 绑死。

## 10. 建议文件边界

建议引入以下模块：

- `temu_y2_women/public_signal_refresh.py`
  - run orchestrator
- `temu_y2_women/public_source_registry.py`
  - registry loading / validation
- `temu_y2_women/public_source_adapter.py`
  - adapter interface
- `temu_y2_women/public_source_adapters/`
  - source-specific adapter implementation
- `temu_y2_women/canonical_signal_builder.py`
  - raw snapshot -> canonical signals
- `temu_y2_women/public_signal_refresh_cli.py`
  - manual refresh entrypoint

建议配置文件：

- `data/refresh/dress/source_registry.json`

第一版不强行抽象过度；只要保持 source adapter 与 canonical builder 的边界清晰即可。

## 11. 测试策略

### 11.1 Adapter 单测

使用本地 fixture HTML 或 recorded source snapshot，验证：

- 能抽到标题、正文块、source metadata
- 缺字段时给出稳定错误
- source-specific 清洗规则可重复

测试不依赖实时联网。

### 11.2 Canonical builder 单测

验证：

- raw snapshot -> canonical signal shape 正确
- season / occasion / manual tags 归一正确
- `price_band_resolution` 正确记录 fallback
- warnings / confidence / provenance 被保留

### 11.3 Compatibility layer 单测

验证：

- canonical signals -> `signal_bundle.json` 映射正确
- 结果能被现有 `signal_ingestion` 直接消费
- richer 字段不会破坏旧链路

### 11.4 端到端集成测试

用 recorded fixture 跑通：

```text
source registry snapshot
-> raw source snapshot
-> canonical_signals.json
-> signal_bundle.json
-> normalized_signals.json
-> draft_elements.json
-> draft_strategy_hints.json
-> refresh_report.json
```

断言：

- active evidence 未被修改
- staged artifacts 全部生成
- 至少产出一批可 review 的 draft elements

## 12. 第一版完成标准

完成后，系统应满足：

1. 能配置并运行 1 个真实公开季节/节日主题文本源
2. 能生成独立 refresh run 目录
3. `canonical_signals.json` 与 `signal_bundle.json` contract 稳定
4. 现有 `signal_ingestion` 可无改动消费该 bundle
5. 能产出 `draft_elements.json` 与 `draft_strategy_hints.json`
6. active evidence 仍只通过 review gate 进入主链

第一版真正落地后，用户将能看到这条可实验链路：

```text
public seasonal source
-> canonical signals
-> staged draft elements
-> review
-> promotion
-> next concept run sees new evidence
```
