# Public Roundup Image Refresh 设计稿

整理日期：2026-04-28

## 1. 目标

当前项目已经具备两段稳定链路：

```text
public editorial text source
-> raw source snapshot
-> canonical signals
-> signal bundle
-> signal_ingestion
```

```text
signal bundle
-> draft_elements / draft_strategy_hints
-> review / promotion
-> active evidence
```

这次 change 的目标，是在现有公开源刷新框架内补上一条最小可用的**商品 roundup 图片观察链路**：

```text
public roundup/list page
-> raw source snapshot
-> card extraction
-> card observations
-> page-level aggregated canonical signals
-> signal bundle
-> signal_ingestion
-> staged draft evidence
```

完成后，系统可以从 1 个真实公开的商品 roundup/list page 中抽取商品卡片，基于卡片图片观察客观 dress slots，把页面级重复出现的 slot/value 聚合为可审阅的 canonical signals，并继续复用现有 ingestion、review、promotion 主链。

## 2. 范围

### 2.1 包含

1. 支持 1 个真实公开的商品 roundup/list page source
2. 在现有 `source_registry` 中显式声明 source pipeline mode
3. 为商品页 source 扩展 `raw_source_snapshot`
4. 新增 `card_observations` 中间产物
5. 基于页面内重复出现的 slot/value 生成页面级 canonical signals
6. 将商品页 source 与现有 editorial text source 纳入同一轮 refresh run
7. 支持手动触发
8. 支持 source-level `card_limit` 与 `aggregation_threshold` 配置
9. 允许图片观察对单个 slot `abstain`

### 2.2 不包含

- 自动 promotion 到 active evidence
- 多 market
- 多 category
- 商品详情页抓取
- 真实价格抽取
- 跨页或跨源全局热点计算
- 复杂 confidence 标定
- 生产级面料 / 工艺 / 尺寸推断
- 图片直接生成 prompt
- 真实图片模型调用进入 CI 或单元测试主链

## 3. 关键设计决定

### 3.1 首个图片源选择“公开商品 roundup/list page”，不直接接零售 bestseller grid

第一版要验证的是：

```text
list page
-> card extraction
-> image observation
-> evidence aggregation
```

商品 roundup/list page 比零售 bestseller grid 更适合 MVP，因为：

- 公开可访问性更高
- 页面结构通常更稳定
- 卡片标题、排序和图片链接更容易抽取
- 联网调试成本更低

### 3.2 图片负责客观 slot 观察，文本只补元数据

商品卡片上的标题和短文案不参与 slot 判定。  
文本只补：

- `title`
- `source_url`
- `rank`
- 页面上下文 tags

客观 slot 由图片观察通道负责，避免“标题词主导元素”的噪声重新回流到系统。

### 3.3 图片观察必须允许 `abstain`

图片观察不强制为每个白名单 slot 都输出结论。  
若图上不可见、分辨率不足或模型不确定，则该 slot 直接 abstain。

这样可以把：

- “看不清”
- “不确定”
- “没有这个元素”

区分开，而不是强行提高误判率。

### 3.4 `card_observations` 是强制中间层，不能直接从卡片跳到 canonical

如果跳过 `card_observations`，后续无法稳定区分：

- 页面解析错误
- 图片观察错误
- 聚合规则错误

因此第一版必须把每张卡的观察结果单独落盘，作为可审计中间产物。

### 3.5 canonical signals 只保留页面级聚合结果

卡片级明细保留在 `card_observations`。  
canonical 层只保留页面级重复出现、达阈值的 slot/value。

切分规则固定为：

- 每个达阈值的 `slot/value` 各产 1 条 canonical signal

这保证后续仍可稳定复用现有 `signal bundle -> ingestion` 链路。

### 3.6 每条聚合 signal 强制保留 `supporting_card_ids`

页面级聚合 signal 必须保留：

- `supporting_card_ids`
- `supporting_card_count`

这样后续做误判排查、规则升级、人工 review 时，都能回溯到具体支持该 signal 的卡片集合。

### 3.7 `card_limit` 与 `aggregation_threshold` 做成 source 配置，默认值分别为 `12` 和 `2`

第一版不做复杂动态调参。  
先用 source-level 配置满足两个目标：

- 控制图片观察成本
- 抑制单卡噪声直接进入 evidence

默认规则：

- 单页最多观察前 `12` 张 card
- 同页内某个 `slot/value` 至少在 `2` 张 card 上重复出现，才进入 canonical

### 3.8 真实图片模型调用不进入主测试链

主线测试必须可离线、可重复。  
因此：

- 单元测试使用 fake / recorded observer
- 联网 `gpt-image-2` 或兼容网关只作为手动 smoke 验证

## 4. 架构

### 4.1 Source registry

在现有 source 元数据上，新增最小路由配置：

- `pipeline_mode`
  - `editorial_text`
  - `roundup_image_cards`
- `card_limit`
- `aggregation_threshold`
- `observation_model`

这让 refresh orchestrator 不再依赖 `adapter_id` 猜行为，而是显式按 source mode 分流。

### 4.2 Source adapter

adapter 继续只负责页面解析。  
对商品 roundup/list page，adapter 的输出是扩展后的 `raw_source_snapshot`，至少包含：

- 页面级元数据
- card 列表

每张 card 至少包含：

- `card_id`
- `rank`
- `title`
- `image_url`
- `source_url`

adapter 不负责：

- 图片观察
- canonical 聚合
- review / promotion

### 4.3 Card observer

新增独立 observer 层，例如 `public_card_observer.py`。  
职责：

- 读取商品页 `raw_source_snapshot`
- 遍历前 `card_limit` 张 card
- 基于 card 图片输出 `card_observations`

observer 只允许输出以下白名单 slot：

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

### 4.4 Roundup canonical builder

商品图片聚合逻辑不并入现有 `canonical_signal_builder.py`。  
新增独立 builder，例如 `roundup_canonical_signal_builder.py`。

职责：

- 输入：
  - `raw_source_snapshot`
  - `card_observations`
  - `aggregation_threshold`
  - `default_price_band`
- 输出：
  - 页面级聚合后的 `canonical-signals-v1`

### 4.5 Refresh orchestrator

`public_signal_refresh.py` 升级为按 source mode 分流的 orchestrator：

```text
load registry
-> for each source
     fetch html
     -> adapter parse raw snapshot
     -> if editorial_text
          build canonical signals directly
        else if roundup_image_cards
          build card observations
          -> aggregate page-level canonical signals
-> merge canonical signals
-> build signal bundle
-> ingest
-> write refresh artifacts / report
```

### 4.6 Ingestion / review / promotion 不变

商品图片链路只扩上游证据获取能力。  
下游仍保持：

- canonical signals
- signal bundle
- signal_ingestion
- review / promotion

active evidence 只通过现有 review-gated workflow 进入主链。

## 5. 产物与 contract

### 5.1 扩展 `raw_source_snapshot`

商品页 source 的 snapshot 至少包含：

- `schema_version`
- `source_id`
- `source_type`
- `source_url`
- `target_market`
- `category`
- `fetched_at`
- `page_title`
- `page_context_tags`
- `cards`

其中 `cards[]` 每项至少包含：

- `card_id`
- `rank`
- `title`
- `image_url`
- `source_url`
- `price_text`
- `brand_text`
- `badges`

原则：

- 先原样采集
- 不在 snapshot 层做语义判断

### 5.2 新增 `card_observations`

建议结构：

- `schema_version`
- `source_id`
- `source_url`
- `fetched_at`
- `observation_model`
- `card_limit`
- `cards`

其中 `cards[]` 每项至少包含：

- `card_id`
- `rank`
- `title`
- `image_url`
- `source_url`
- `observed_slots`
- `abstained_slots`
- `warnings`

`observed_slots[]` 每项至少包含：

- `slot`
- `value`
- `evidence_summary`

第一版不强制数值 `confidence`。  
若后续证明兼容网关能稳定输出可用置信度，再考虑加入。

### 5.3 页面级聚合 canonical signal

每条聚合 signal 至少包含现有 `canonical-signals-v1` 必需字段，并在 `extraction_provenance` 中增加：

- `aggregation_kind = "roundup_card_slot_aggregation"`
- `slot`
- `value`
- `supporting_card_ids`
- `supporting_card_count`
- `card_limit`
- `aggregation_threshold`
- `adapter_version`
- `observation_model`
- `warnings`

为避免 contract 含糊，商品页聚合 signal 采用以下确定性生成规则：

- `title`
  - 使用页面 `page_title`
- `summary`
  - 使用模板：`Observed <slot>=<value> across <supporting_card_count> roundup cards.`
- `evidence_excerpt`
  - 取前 3 个 supporting cards 的 `title`，按 ` | ` 拼接
- `manual_tags`
  - 使用页面级 `page_context_tags`
- `observed_price_band`
  - 第一版固定走 source default
- `price_band_resolution`
  - 固定为 `source_default`
- `status`
  - 固定为 `active`

### 5.4 `refresh_report` 扩展字段

为商品页 source 增加统计字段：

- `card_count_extracted`
- `card_count_observed`
- `card_limit`
- `aggregation_threshold`
- `aggregated_signal_count`
- `abstention_summary`
- `image_observation_warning_count`

这样 refresh report 能直接回答：

- 页面抽到了多少 card
- 实际观察了多少张
- 模型在哪些 slot 上大量 abstain
- 最终有多少聚合 signal 进入 canonical

### 5.5 `signal-bundle-v1` compatibility

商品页聚合 canonical signals 继续映射到现有 `signal-bundle-v1`：

- `signal_id = canonical_signal_id`
- `title = page_title`
- `summary = canonical summary`
- `manual_tags / season / occasion / price_band` 直接映射

兼容层不引入新的 ingestion contract 改动。

## 6. 与现有 refresh 框架的接线方式

### 6.1 双源、双通道、单落点

第一版 refresh run 同时允许：

- 1 个 editorial text source
- 1 个 roundup image source

两条通道都落到统一 `canonical_signals.json`，再进入统一 `signal_bundle.json` 与 `signal_ingestion`。

### 6.2 输出目录

一次 refresh run 至少包含：

- `source_registry_snapshot.json`
- `raw_sources/`
- `card_observations/`
- `canonical_signals.json`
- `signal_bundle.json`
- `normalized_signals.json`
- `draft_elements.json`
- `draft_strategy_hints.json`
- `ingestion_report.json`
- `refresh_report.json`

文本源不会写 `card_observations`。  
商品页源会额外写对应 observation 文件。

## 7. 测试策略

### 7.1 Adapter fixture 测试

给定 roundup/list page HTML fixture，稳定抽出 card 列表。  
只验证页面解析，不验证图片观察。

### 7.2 Card observation fixture 测试

给定固定 card 列表，使用 fake / recorded observer 生成 `card_observations`。  
重点验证：

- 只出现白名单 slot
- 允许 `abstain`
- 不强制每个 slot 出值

### 7.3 Aggregation / canonical 测试

给定固定 `card_observations`，按 `aggregation_threshold=2` 聚合。  
重点验证：

- 每个达阈值的 `slot/value` 各产 1 条 signal
- `supporting_card_ids` 正确保留
- 低于阈值的结果不会进入 canonical

### 7.4 Refresh orchestration 测试

同一轮 refresh 同时跑：

- 1 个 editorial text source
- 1 个 roundup image source

验证统一 refresh 输出和 report 字段。

### 7.5 联网 smoke 验证

真实 `gpt-image-2` 或兼容网关调用仅保留手动 smoke 验证入口，不进入单元测试主链。

## 8. 实施切分

### Task A：roundup adapter + raw snapshot

范围：

- registry 增配
- roundup adapter
- raw snapshot fixtures
- adapter tests

目标：

- 稳定抽出商品卡片列表

### Task B：card observations + aggregation builder

范围：

- observer interface
- fake / recorded observer
- `card_observations` contract
- page aggregation to canonical signals
- 对应 fixtures 与 tests

目标：

- 离线跑通 `cards -> observations -> canonical signals`

### Task C：refresh orchestration 接线

范围：

- `public_signal_refresh.py` 分流
- mixed-source refresh artifacts
- report 扩展
- orchestration tests

目标：

- 文本源与商品页图片源共存于同一轮 refresh

## 9. Guardrails

- 不改 active evidence 写入规则
- 不让图片通道直接写 `elements.json`
- 不把图片模型联网调用耦死在单元测试中
- 不把商品图片聚合逻辑塞进现有 `canonical_signal_builder.py`
- 不在第一版引入生产级元数据推断
