# Public Multi-Source Expansion 设计稿

整理日期：2026-04-28

## 1. 目标

当前仓库已经具备单个公开文本趋势源的最小刷新链路：

```text
public source
-> raw source snapshot
-> canonical signals
-> signal bundle
-> signal_ingestion
-> staged drafts
```

这次 change 的目标，是把它扩成一条可调试、可分源观测的多源刷新链路：

```text
selected public sources
-> source selection
-> raw source snapshots
-> canonical signals
-> merged signal bundle
-> signal_ingestion
-> staged drafts
-> source-level refresh report
```

完成后，系统应支持 2 个公开文本趋势源并行刷新，其中：

- 1 个同构源：Who What Wear dress trend editorial
- 1 个异构源：Marie Claire dress trend editorial

## 2. 范围

### 2.1 包含

1. 把 source registry 从 1 源扩成 2 源
2. 支持手动 refresh 时按 `--source-id` 只跑指定 source
3. 在 refresh report 中补齐 per-source 状态、coverage、weight、priority
4. 把当前偏单源的 canonical provenance 规则拆成可按 source 扩展的结构
5. 接入 1 个同构 source 与 1 个异构 source

### 2.2 不包含

- 零售榜单或商品详情页抓取
- `weight` 参与 signal/draft 排序
- 自动 promotion 到 active evidence
- 多 category / 多 market
- 通用 DSL 式 parser 配置系统

## 3. Source 选择

### 3.1 同构 source

- `whowhatwear-summer-2025-dress-trends`
- `whowhatwear-summer-dress-trends-2025`

两者都来自 Who What Wear，优先验证：

- registry 多源选择
- 同站点 adapter 复用
- source-specific profile 差异配置

### 3.2 异构 source

- `marieclaire-summer-2025-dress-trends`

该源用于验证：

- 新 adapter 的接入边界
- 非 Who What Wear 页面结构下的 snapshot 提取
- 分源 coverage 汇总逻辑

## 4. 关键设计决定

### 4.1 保留主链，新增 source selection

refresh 主链继续复用现有：

- registry load
- adapter parse
- canonical builder
- bundle builder
- signal ingestion

新增一层 source selection：

- 默认选中所有 enabled source
- 支持 CLI 传入多个 `--source-id`
- 指定 source 不存在或未启用时 fail-closed

### 4.2 registry 只扩运营元数据，不塞 parser DSL

registry 新增：

- `priority`
- `weight`

它们本轮只用于：

- selection snapshot
- refresh report
- 后续 review 参考

不参与 draft element 聚合和排序。

### 4.3 source-specific 规则下沉到 profile / adapter 层

当前 `canonical_signal_builder.py` 中存在明显单源耦合：

- 固定 section confidence
- 固定 evidence rule 语料
- provenance 里的 `adapter_version`

本次要把这些信息改成从 snapshot 或 source profile 派生，避免继续把 Who What Wear 规则写死在通用 builder 中。

### 4.4 refresh report 必须具备分源可解释性

总览层保留，但新增 per-source 明细，至少记录：

- source status
- signal count
- matched / unmatched count
- fallback price-band count
- warnings / errors
- configured priority / weight

## 5. 架构

### 5.1 Source registry

继续维护启用源列表，但每条记录新增：

- `priority: int`
- `weight: float`

### 5.2 Source selection

新增集中选择逻辑，职责：

- 过滤 enabled source
- 校验 CLI 传入的 `source_ids`
- 产出本次 run 的 selected source list

### 5.3 Adapter layer

保留 adapter resolution 边界：

- Who What Wear 继续走 editorial adapter
- Marie Claire 新增独立 editorial adapter

同构源尽量复用已有解析骨架，不把页面差异扩散到 runner 中。

### 5.4 Canonical builder

通用 builder 继续负责：

- snapshot contract 校验
- signal contract 生成
- signal bundle compatibility

但 provenance 字段改为从 snapshot section metadata 派生，而不是通用层写死单一 adapter 信息。

### 5.5 Refresh reporting

report 分为两层：

1. run summary
2. source details

并增加：

- `selected_source_ids`
- `source_details`

## 6. Contract 变化

### 6.1 registry

每个 source record 新增：

- `priority`
- `weight`

### 6.2 CLI

`public_signal_refresh_cli.py run` 新增：

- `--source-id`，可重复传入

### 6.3 refresh report

新增字段：

- `selected_source_ids`
- `source_details`

`source_details[]` 至少包含：

- `source_id`
- `adapter_id`
- `priority`
- `weight`
- `status`
- `signal_count`
- `matched_signal_count`
- `unmatched_signal_count`
- `fallback_price_band_count`
- `warnings`
- `errors`

### 6.4 canonical snapshot expectations

raw snapshot 中每个 section 需要允许 adapter 携带 provenance hints，例如：

- `section_id`
- `heading`
- `text`
- `tags`
- `confidence`
- `matched_keywords`
- `excerpt_anchor`
- `adapter_version`

通用 builder 只消费这些字段，不再保存 Who What Wear 专属常量。

## 7. 测试策略

### 7.1 Registry / selection tests

覆盖：

- priority / weight 校验
- 默认全量 source 选择
- 指定 `--source-id` 的成功路径
- 指定不存在 / disabled source 的失败路径

### 7.2 Adapter tests

覆盖：

- 新增 Who What Wear 同构源 fixture
- 新增 Marie Claire fixture
- 两个 adapter 都能产出稳定 snapshot

### 7.3 Canonical builder tests

覆盖：

- provenance 从 snapshot section metadata 派生
- 多源 signal 能稳定进入同一 canonical contract

### 7.4 Refresh integration tests

覆盖：

- 2 源全量 refresh
- 指定单源 refresh
- 分源错误不阻断其他源
- report 中 source details 与 coverage 正确

## 8. 完成标准

完成后，仓库应满足：

1. registry 可配置 2 个公开文本趋势源
2. CLI 可跑全量源，也可按 `--source-id` 定向回放
3. refresh run 能稳定产出 merged staged artifacts
4. refresh report 能说明每个 source 的产出和命中质量
5. `weight` / `priority` 已进入 contract，但尚未影响 draft 排序
6. 现有 active evidence 仍不被 refresh 直接改写
