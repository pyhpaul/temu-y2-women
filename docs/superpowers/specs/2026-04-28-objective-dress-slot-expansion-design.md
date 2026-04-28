# Objective Dress Slot Expansion 设计稿

整理日期：2026-04-28

## 1. 背景与目标

当前 `dress` 主链虽然已经具备：

- active evidence 检索
- 受控组合
- prompt bundle 输出
- 6 图渲染链路

但 active slot 仍然过少，导致两个直接问题：

1. **概念层差异不足**：即使换 request，核心结构仍容易收敛到相近轮廓。
2. **成图层差异不足**：prompt 缺少能稳定拉开视觉差异的客观属性。

这次 change 的目标，不是引入更多主观“设计感词”，而是把系统扩成：

```text
客观服装属性 taxonomy
-> active elements / strategy preferences
-> 受控组合
-> 可解释 prompt
-> 更有差异的成图
```

完成后，系统应满足：

- 新增一批**客观、可枚举、可被公开 source 映射**的 dress slot
- slot 的“是否热门”继续由 evidence 决定，而不是主观审美判断
- 组合结果能明显拉开主图与细节图差异
- refresh 链路后续可以自动补充这些新 slot 的 evidence

## 2. 范围

### 2.1 包含

1. 扩展 `dress` evidence taxonomy 的 allowed slots
2. 为新增 slot 建立最小 active baseline elements
3. 扩展组合器，让新增 slot 能进入 `selected_elements`
4. 扩展 prompt / factory spec，让新增 slot 进入出图与工厂草案
5. 扩展 signal phrase rules 与 canonical fixtures，让 refresh 后续能抽到这些 slot
6. 为新增 slot 建立最小依赖 / 冲突规则

### 2.2 不包含

- 主观风格词，如 `romantic vibe`、`quiet luxury`、`effortless chic`
- 全局审美求解器或复杂搭配引擎
- 更细的工厂生产参数，如完整 BOM、尺码表、克重、缝份
- 依赖 `images.edit` 稳定性的图像一致性强化策略

## 3. 设计原则

### 3.1 slot 必须是客观服装属性

slot 只允许进入这类信息：

- 商品属性
- 结构属性
- 表面属性
- 可直接被 source 文本命名的客观值

不允许把“审美判断”本身做成 slot。

### 3.2 taxonomy 决定“能选什么”，evidence 决定“更常选什么”

系统分两层：

1. **taxonomy / baseline 层**
   - 定义有哪些合法 slot/value
   - 提供最小可运行的 active baseline
2. **evidence / refresh 层**
   - 根据公开 source 提升或新增特定 slot/value
   - 影响 `base_score`、`slot_preferences`、draft promotion

这样可以避免把系统变成“人工主观搭配器”。

### 3.3 优先选择“强视觉差异 + 强证据映射”的 slot

新增 slot 必须同时满足：

1. **视觉差异强**：能明显改变成图
2. **语义客观**：值边界清晰
3. **source 可映射**：能从公开 editorial 文本稳定提取

### 3.4 组合器只做受控搜索，不做开放式创作

本轮仍坚持：

- required slot 保持简单
- optional slot 做有限搜索
- 兼容性规则必须可解释
- 不引入黑盒式“设计感打分器”

## 4. 第一批新增 slot

在 exploration 阶段曾讨论过 `hem_shape`、`strap_type` 等方向。  
结合当前公开 source fixture 覆盖后，本轮第一批 slot 调整为**更易证据落地**的一组：

- `dress_length`
- `waistline`
- `color_family`
- `print_scale`
- `opacity_level`

原因：

- 这 5 个 slot 都能明显拉开成图差异
- 当前 fixture 已经能找到较直接的文本证据
- 比 `hem_shape`、`strap_type` 更容易减少主观解释空间

### 4.1 Phase 1 slot/value 基线

| slot | Phase 1 active baseline values | 说明 |
| --- | --- | --- |
| `dress_length` | `mini`, `midi` | 直接影响整体比例 |
| `waistline` | `natural waist`, `drop waist` | 直接影响结构识别 |
| `color_family` | `white`, `red` | 直接影响第一眼识别 |
| `print_scale` | `micro print`, `oversized print` | 直接影响表面节奏 |
| `opacity_level` | `opaque`, `sheer` | 直接影响材质观感与细节图差异 |

### 4.2 本轮明确延期的 slot

以下 slot 不在本轮首批落地：

- `hem_shape`
- `strap_type`
- `texture`
- `trim_detail`

延期原因：

- 当前 fixture 中直接证据不足或覆盖偏稀
- 容易在 Phase 1 被主观解释放大
- 先落地本轮 5 个 slot，更容易快速验证效果

## 5. 对现有 slot 的配套扩展

只加新 slot 还不够。为了避免新 slot 进入后仍然被旧 evidence 收敛，本轮同步扩展少量现有 slot 值：

- `pattern`：新增 `polka dot`
- `detail`：新增 `neck scarf`

说明：

- `polka dot` 已在 Who What Wear 与 Marie Claire fixture 中出现
- `neck scarf` 在 Who What Wear 原文里已有明确趋势描述

这两个扩展不改变“新增 slot 是主线”的定位，但能显著帮助新 slot 产生更强的画面差异。

## 6. 架构变化

### 6.1 evidence taxonomy

`data/mvp/dress/evidence_taxonomy.json` 需要：

- 扩展 `allowed_slots`
- 扩展 `allowed_tags`
- 允许新 slot 的值进入 active evidence、strategy、draft promotion

本轮不新增新的复杂 taxonomy 结构，继续复用现有 schema。

### 6.2 active elements baseline

`data/mvp/dress/elements.json` 需要新增：

- 每个新 slot 至少 2 个 active values
- 与现有 `price_bands / occasion_tags / season_tags / risk_flags` 保持同构

基线原则：

- **有明确证据的值**：用更高 `base_score`
- **作为对照的中性值**：保留较低但可选的 `base_score`

例如：

- `drop waist` 得分高于 `natural waist`
- `sheer` 与 `opaque` 共存，但不强行让 `sheer` 成为默认

### 6.3 strategy templates

`data/mvp/dress/strategy_templates.json` 需要支持新 slot 的 `slot_preferences`：

- 可偏好 `dress_length`
- 可偏好 `waistline`
- 可偏好 `color_family`
- 可偏好 `print_scale`
- 可偏好 `opacity_level`

本轮不引入新的 strategy schema，仅扩展可引用的 slot/value。

### 6.4 retrieval / scoring

`evidence_repository.retrieve_candidates()` 主流程可以继续复用。  
新增 slot 后，变化点主要是：

- 能返回更多 slot 的 candidates
- strategy matching 能命中新 slot 的 `slot_preferences`
- flatten / report 输出中会自然出现新 slot

也就是说，检索层不需要重写，只需要保证 taxonomy 与 active evidence 已接受新 slot。

### 6.5 composition engine

组合器是本轮关键变化点。

现状：

- required: `silhouette`, `fabric`
- standard optional: `neckline`, `sleeve`
- bounded search: `pattern`, `detail`

本轮调整为：

- required:
  - `silhouette`
  - `fabric`
- standard optional:
  - `neckline`
  - `sleeve`
  - `dress_length`
  - `waistline`
  - `color_family`
  - `opacity_level`
- bounded search group:
  - `pattern`
  - `print_scale`
  - `detail`

原因：

- `dress_length / waistline / color_family / opacity_level` 可先用 top-1 贪心选取
- `print_scale` 强依赖 `pattern`
- `detail` 已经存在与 `pattern` 的兼容性基础
- 把 `pattern / print_scale / detail` 放在同一个小搜索组里，能避免明显冲突，又不会升级成全局求解器

### 6.6 compatibility / dependency rules

本轮只引入**可解释、结构性的最小规则**：

1. `print_scale` **依赖** `pattern`
   - 没有 pattern 时，不选 print_scale
2. `waistline=drop waist` 与 `silhouette=bodycon` 视为强冲突
   - 理由是结构表达冲突，而不是审美判断
3. 现有 `pattern/detail` 兼容性规则继续保留
4. `opacity_level` 先不引入复杂审美规则
   - 只作为可选客观属性进入组合

本轮不做：

- 任意 slot 两两打分
- 风格学上的“打架”判断
- LLM 审美仲裁

### 6.7 prompt renderer

`prompt_renderer.py` 必须显式消费新增 slot。  
否则概念层虽然变了，成图层仍会相似。

本轮要求：

- `[核心结构]` 补充 `dress_length`、`waistline`
- `[面料与工艺表现]` 补充 `color_family`、`print_scale`、`opacity_level`
- detail jobs 显式引用相关 slot

建议映射：

- `hero_*`
  - 重点展示整体比例、腰线、颜色与透明度
- `construction_closeup`
  - 强调 `waistline`、`detail`、`neckline`
- `fabric_print_closeup`
  - 强调 `pattern`、`print_scale`、`opacity_level`
- `hem_and_drape_closeup`
  - 强调 `dress_length` 对下摆比例和垂感的影响

### 6.8 factory spec builder

`factory_spec_builder.py` 需要把新增 slot 进入：

- `known.selected_elements`
- `inferred.fit_review_cues`
- `inferred.visible_construction_checks`
- `inferred.commercial_review_cues`

这里仍然只输出**生产草案级已知信息**，不假装生成完整工厂参数。

## 7. refresh / public source 接入设计

### 7.1 为什么这条线要一起设计

如果只改 `elements.json`，短期能看到差异，但系统仍会停留在“手工补元素库”。  
用户的目标是最终从公开 source 自动吸收热点元素，因此这轮必须把 refresh 接口一起设计清楚。

### 7.2 canonical / phrase rules 的角色

本轮仍复用：

```text
public source snapshot
-> canonical signals
-> signal bundle
-> signal_ingestion
-> draft elements / draft strategy hints
```

变化点主要在：

- `signal_phrase_rules.json`
- fixture coverage
- promotion 后的新 slot 能进入 active elements

### 7.3 Phase 1 直接映射的公开文本短语

第一批优先映射这些短语：

| phrase example | mapped slot/value |
| --- | --- |
| `mini`, `minis` | `dress_length=mini` |
| `midi`, `midis` | `dress_length=midi` |
| `drop-waist`, `drop waist` | `waistline=drop waist` |
| `white dress`, `white dresses` | `color_family=white` |
| `red dress`, `red sundress`, `red-hot` | `color_family=red` |
| `micro-dot`, `micro dot` | `print_scale=micro print` |
| `oversize print`, `oversized print` | `print_scale=oversized print` |
| `sheer` | `opacity_level=sheer` |

### 7.4 中性 baseline 值的来源

并不是每个 active baseline 值都必须先在当前 fixture 里被明确提到。  
例如：

- `natural waist`
- `opaque`

这类值可以作为**中性对照值**存在于 baseline 中，满足：

- taxonomy 合法
- 商品属性客观
- 不依赖主观判断

但只有当 refresh 证据出现时，相关值才应该被更强地提升或新增。

## 8. 这轮为什么不依赖图片 edit 稳定性

当前 `images.edit` 在兼容网关上存在不稳定性或账号池问题。  
这不影响本轮 slot 设计成立，因为本轮的核心验证指标是：

1. `selected_elements` 是否明显更丰富
2. prompt 是否显式携带新 slot
3. 即便只跑单图 generate，输出 prompt 也已经更有差异

因此：

- slot 扩展主线继续推进
- image edit 稳定性排查作为并行问题处理

## 9. 测试策略

### 9.1 taxonomy / evidence validation

覆盖：

- 新 slot 进入 `allowed_slots`
- 新 tags 不触发非法 taxonomy
- active element / strategy fixture 能通过现有 validation

### 9.2 composition tests

覆盖：

- 新 slot 能进入 `selected_elements`
- `print_scale` 在没有 `pattern` 时被省略
- `drop waist + bodycon` 触发强冲突
- 新 slot 不破坏现有 required slot 与 must-have 逻辑

### 9.3 prompt / factory spec tests

覆盖：

- render prompt 显式包含 `dress_length / waistline / color_family / print_scale / opacity_level`
- detail prompts 读取对应 slot
- factory spec 的 known / inferred 段落包含新增 slot 影响

### 9.4 refresh / ingestion tests

覆盖：

- 新 phrase rules 可进入 draft elements
- canonical snapshot / signal bundle / ingestion 主链仍可跑通
- promotion 后新 slot/value 能写回 active evidence

## 10. 实施拆分

这次 change 建议拆成两个并行 change：

### Change A：Objective slot baseline + composition + prompt

包含：

- taxonomy
- elements / strategy templates
- composition engine
- prompt renderer
- factory spec builder
- 相关测试

目标：

- 尽快把“图像总是类似”的根因打掉

### Change B：Refresh extraction for new slots

包含：

- signal phrase rules
- canonical signal fixtures
- public source fixture / adapter coverage
- promotion / experiment compatibility

目标：

- 把新 slot 从“人工基线”升级成“可自动扩展的 evidence 体系”

两个 change 可以并行开发；  
其中 Change A 不依赖 `images.edit` 稳定。

## 11. 完成标准

完成后，仓库应满足：

1. `dress` taxonomy 至少新增 5 个客观 slot
2. active baseline 至少为每个新 slot 提供 2 个可运行 values
3. 组合结果 `selected_elements` 中能稳定出现新 slot
4. prompt bundle 能显式消费这些新 slot
5. factory spec 草案能带出这些新 slot 的已知信息
6. refresh 设计已具备把公开趋势短语映射到新 slot 的清晰路径
7. 系统仍然保持“evidence 决定热度、组合器受控搜索”的非主观路线
