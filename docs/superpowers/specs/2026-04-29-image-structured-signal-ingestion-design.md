# Public Image Structured Signal Ingestion 设计稿

整理日期：2026-04-29

## 1. 目标

当前项目已经具备以下稳定主链：

```text
public source
-> canonical signals
-> signal bundle
-> signal_ingestion
-> draft_elements / draft_strategy_hints
-> review / promotion
-> active evidence
```

这次 change 的目标，是把**公开商品卡图**正式接成 `signal_ingestion` 的一级输入通道，让图片观察结果不再绕回文本短语匹配，而是以结构化候选的形式进入 draft evidence 主链。

完成后，系统应能支持：

```text
public roundup/list page
-> card extraction
-> card image observation
-> page-level slot/value aggregation
-> structured signal candidates
-> signal_ingestion
-> draft_elements
```

其中最关键的新增能力是：

1. 图片链路可直接驱动 `draft_elements`
2. 图片链路允许提出**新 value 候选**
3. 新 value 只进入 `draft / review`，不直接进入 active evidence

## 2. 范围

### 2.1 包含

1. 只支持现有公开 source 体系中的商品 roundup/list page
2. 只支持客观 dress slot/value 候选
3. `signal_ingestion` 升级为文本 + 结构化图片候选双通道
4. 允许图片链路提出未出现在当前 phrase rules 中的新 value
5. 保持现有 review / promotion 主链不变
6. 为 refresh / ingestion / draft 输出补充可追溯 provenance

### 2.2 不包含

1. 手动上传本地商品图做元素入池
2. trend / vibe / style keyword 这类主观判断
3. 新 slot 自动发现
4. 新 value 自动进入 active evidence
5. 新 value 自动生成主观风格 tags
6. 生产级面料、工艺、尺寸推断
7. 图片生成工作流改造

## 3. 当前缺口

当前 `public_card_observer` 与 `roundup_canonical_signal_builder` 已经能把公开商品卡图观察成页面级 slot/value 聚合结果，但 `signal_ingestion` 仍然主要依赖 `signal_phrase_rules.json` 从 `title + summary + tags` 中做短语命中。

这导致两个问题：

1. 图片观察结果必须绕回文本，链路语义不干净
2. phrase rules 不认识的新 value 无法稳定进入 `draft_elements`

因此，这次 change 的本质不是“再加一点 observer 输出”，而是把 ingestion 的输入契约从“纯文本信号”升级为“文本信号 + 结构化图片候选”。

## 4. 关键设计决定

### 4.1 `signal_ingestion` 改为双通道，而不是让图片结果回写文本

新增结构化图片候选通道：

- 文本 source 继续走现有 phrase rule 通道
- 图片 source 允许直接携带 `structured_candidates`
- 两个通道统一聚合成 draft elements

不采用“把图片结果拼回 summary/title 再让 phrase rules 猜一次”的方案，因为那会让图片链路继续受文本词表约束，无法稳定支持新 value 入池。

### 4.2 只开放 `value`，不开放 `slot`

第一阶段固定 slot 白名单，允许开放 value：

- `silhouette`
- `neckline`
- `sleeve`
- `dress_length`
- `pattern`
- `color_family`
- `waistline`
- `print_scale`
- `opacity_level`
- `detail`

这样可以获得扩元素库的收益，同时避免把系统扩成“任意新 slot 都可入池”。

### 4.3 新 value 只进入 `draft / review`

图片链路提出的新 value：

- 可以进入 `draft_elements.json`
- 可以进入 review 模板
- 只有在 reviewer 接受后，才可能被 promotion 创建为 active element

这保持了现有 evidence 治理边界：

```text
ingestion 负责提出候选
review / promotion 负责决定是否纳入元素库
```

### 4.4 `tags` 采用保守策略，不自动注入主观设计感

对图片结构化候选：

- `price_bands / occasion_tags / season_tags` 可继承 signal 上下文
- 语义 `tags` 只在 `(slot, value)` 已知时复用现有规则
- 对新 value 不自动补 `romantic / feminine / airy` 这类主观风格标签

这样可以降低主观判断对元素库扩展的污染。

### 4.5 先不升级 `signal-bundle` 主版本

本次在单条 signal record 上新增**可选字段** `structured_candidates`，但不把 `signal-bundle-v1` 升级到 `v2`。

原因：

1. 保持现有 text source 与 CLI 兼容
2. 降低 fixtures 与测试面的大范围扰动
3. 当前新增能力只对图片派生 source 生效，使用可选字段即可表达

### 4.6 结构化候选 fail-closed

一旦 signal 上声明了 `structured_candidates`，就必须满足最小输入契约：

- `slot` 必须在 taxonomy `allowed_slots`
- `value` 必须是非空字符串
- `candidate_source` 必须是受支持常量
- `supporting_card_ids` 必须非空
- `supporting_card_count` 必须与去重后的 `supporting_card_ids` 数量一致
- `aggregation_threshold` 必须是正整数
- `supporting_card_count` 必须满足聚合阈值

结构错误直接返回 `INVALID_SIGNAL_INPUT`，不做静默降级。

## 5. 数据契约

### 5.1 `signal_bundle` 新增可选字段

单条 signal record 允许新增：

```json
"structured_candidates": [
  {
    "slot": "pattern",
    "value": "gingham check",
    "candidate_source": "roundup_card_image_aggregation",
    "supporting_card_ids": ["card-001", "card-004"],
    "supporting_card_count": 2,
    "aggregation_threshold": 2,
    "observation_model": "gpt-4.1-mini",
    "evidence_summary": "Observed pattern=gingham check across 2 roundup cards."
  }
]
```

约束：

1. editorial text source 可以没有该字段
2. roundup image source 可以携带该字段
3. 第一阶段每条 roundup canonical signal 只携带 1 个 candidate

### 5.2 `canonical_signals` 保留聚合语义，但允许携带结构化候选

`roundup_canonical_signal_builder` 输出仍然是页面级聚合 signal：

- `summary`
- `evidence_excerpt`
- `extraction_provenance`

同时为 ingestion 准备结构化消费字段：

- `structured_candidates`

这让“解释字段”和“业务输入字段”保持分离。

### 5.3 `normalized_signals` 保留 `structured_candidates`

`signal_ingestion` 的 normalized output 在现有字段基础上新增：

- `structured_candidates`

归一化内容包括：

- `slot` canonicalize
- `value` trim / casefold / 空白稳定化
- `supporting_card_ids` 去重排序
- `evidence_summary` 去首尾空白

### 5.4 `draft_elements[*].extraction_provenance` 扩展为多通道

第一阶段支持三种 provenance kind：

- `signal-rule-match`
- `structured-signal-candidate`
- `hybrid-signal-candidate`

其中 `structured_matches` 每条至少包含：

- `signal_id`
- `slot`
- `value`
- `candidate_source`
- `supporting_card_ids`
- `supporting_card_count`
- `aggregation_threshold`
- `observation_model`
- `evidence_summary`

## 6. 处理流程

### 6.1 Roundup builder

```text
card observations
-> aggregate by (slot, value)
-> build canonical signal
-> attach one structured candidate to that signal
```

页面级 signal 仍然保留聚合阈值与 supporting cards 语义。

### 6.2 Refresh orchestrator

`public_signal_refresh.py` 只负责透传结构化候选，不重新解释其含义：

```text
canonical signal
-> signal bundle record
-> structured_candidates copied through
```

editorial source 不受影响。

### 6.3 Ingestion dual-channel extraction

对每条 normalized signal：

```text
text channel
-> phrase rule matches
-> rule raw candidates

structured channel
-> structured candidate validation
-> structured raw candidates

merge both channels
-> aggregate by (slot, value)
-> build draft elements
```

### 6.4 聚合规则

统一按 `(slot, value)` 聚合：

1. 文本同值 + 图片同值 -> 合并成 1 条 draft
2. 多图片 source 同值 -> 合并成 1 条 draft
3. 同 slot 不同 value -> 分开保留
4. `abstained_slots` 不作为负样本，不参与冲突判定

## 7. 候选治理规则

### 7.1 最小准入规则

结构化候选进入 ingestion 前，必须满足：

1. `slot` 在 taxonomy 白名单
2. `value` 非空
3. `supporting_card_ids` 非空
4. `candidate_source` 为已支持常量
5. `supporting_card_count == len(unique supporting_card_ids)`
6. `supporting_card_count >= aggregation_threshold`

### 7.2 `tags` 生成策略

#### 已知 `(slot, value)`

如果 `(slot, value)` 能命中已有 phrase rule 或 enrichment lookup：

- 复用该记录已有 `tags`

#### 新 `(slot, value)`

如果是 phrase rules 不认识的新 value：

- `tags = []`
- 仅保留 `price_bands / occasion_tags / season_tags`

### 7.3 分数策略

第一阶段的 `suggested_base_score` 表示证据强度，不表示主观热度：

```text
evidence_count = max(unique_source_signal_count, supporting_card_count)
suggested_base_score = round(0.6 + 0.05 * evidence_count, 2)
cap at 0.8
```

### 7.4 `evidence_summary` 策略

采用客观证据句：

- structured-only：
  - `Observed in 3 roundup cards from 1 public signal for US dress demand.`
- text-only：
  - 保持现有 summary 语义
- hybrid：
  - `Observed in 3 roundup cards and matched in 2 text signals for US dress demand.`

## 8. 模块改造清单

### 8.1 `temu_y2_women/roundup_canonical_signal_builder.py`

新增：

1. 为每条 roundup canonical signal 附加 `structured_candidates`
2. 结构化候选与现有 `extraction_provenance` 共享 supporting cards 基础事实

建议新增 helper：

- `_structured_candidate(...)`
- `_structured_candidate_summary(...)`

### 8.2 `temu_y2_women/public_signal_refresh.py`

新增：

1. `_signal_bundle_record(...)` 透传 `structured_candidates`
2. refresh report 可选补充结构化候选统计

建议新增 helper：

- `_optional_structured_candidates(...)`
- `_signal_bundle_structured_candidate(...)`

### 8.3 `temu_y2_women/signal_ingestion.py`

新增能力：

1. 校验 `structured_candidates`
2. normalization 保留并标准化 `structured_candidates`
3. 从结构化候选直接生成 raw candidates
4. 与文本规则候选统一聚合
5. provenance / score / evidence summary 支持多通道
6. signal outcome 报告支持 `matched_channels`

建议新增 helper：

- `_validate_structured_candidates(...)`
- `_validate_structured_candidate(...)`
- `_normalize_structured_candidates(...)`
- `_build_structured_raw_candidate(...)`
- `_slot_value_tag_lookup(...)`
- `_suggested_base_score(...)`
- `_draft_provenance_kind(...)`

所有新增逻辑都应继续遵守仓库现有约束：函数行数不超过 60，helper 拆分明确。

## 9. 测试计划

### 9.1 兼容性回归

以下现有测试应继续通过，证明 text 主链未被破坏：

- `tests/test_signal_ingestion.py`
- `tests/test_public_signal_refresh.py`
- `tests/test_roundup_canonical_signal_builder.py`

### 9.2 新增 ingestion 单测

至少补以下场景：

1. 合法 `structured_candidates` 可直接产出 draft
2. 新 value 可进入 `draft_elements.json`
3. 同一 `(slot, value)` 的 text + structured 候选会聚合成单条 draft
4. 非法 `structured_candidates` 返回 `INVALID_SIGNAL_INPUT`

### 9.3 新增 roundup builder 测试

至少补以下场景：

1. canonical signal 附带 `structured_candidates`
2. `structured_candidates[*].supporting_card_ids` 与 provenance 一致

### 9.4 新增 refresh 集成测试

补一条 mixed-source end-to-end 测试：

- fake card observer 输出至少 1 个 phrase rules 不认识的新 value
- 最终 `draft_elements.json` 中出现该新 value
- `ingestion_report.json` 中对应 signal 记录 `matched_channels=["structured_candidate"]`

## 10. Phase 拆分

### Phase 1：打通图片结构化候选入池主链

包含：

1. roundup canonical signal 增加 `structured_candidates`
2. signal bundle 透传 `structured_candidates`
3. ingestion 支持 structured channel
4. 新 value 可进入 `draft_elements.json`

### Phase 2：已知 value 轻量 enrichment

包含：

1. 已知 `(slot, value)` 复用现有 tags
2. hybrid provenance 合并
3. score / summary 更清楚地区分 text 与 image

### Phase 3：review / refresh 可读性增强

包含：

1. refresh report 增加 structured candidate 统计
2. review 阶段更清楚展示 candidate 来源、支持卡片数、模型名

## 11. 多 agent 并行方案

并行开发的前提是先锁定以下 contract：

1. `structured_candidates` 字段名
2. candidate 最小 schema
3. `matched_channels` report 结构
4. provenance kind 常量

在这些契约固定后，可按以下职责并行：

### Agent A：builder + refresh 透传

负责：

- `temu_y2_women/roundup_canonical_signal_builder.py`
- `temu_y2_women/public_signal_refresh.py`
- 对应 tests / fixtures

### Agent B：ingestion 双通道

负责：

- `temu_y2_women/signal_ingestion.py`
- ingestion tests / fixtures

### Agent C：集成与回归

负责：

- mixed-source integration fixture
- end-to-end refresh regression
- 函数长度与主回归验证

## 12. 风险与非目标

### 12.1 已知风险

1. 新 value 的命名仍可能受 observer 术语波动影响
2. 第一阶段不做自动别名归并，review 端仍需人工判断是否保留命名
3. 不把 `abstain` 当负样本，意味着第一阶段更偏召回而不是排斥

### 12.2 当前明确不做

1. 用图片链路自动推出主观风格标签
2. 自动判断新 value 是否应并入既有 value
3. 改造图片生成工作流
4. 扩展到手动本地图输入

## 13. 下一步

设计确认后，下一步应进入实现计划阶段，输出：

1. 任务拆分顺序
2. 每个任务的测试先行点
3. 适合并行给子 agent 的文件边界

随后再开始实际代码改造。
