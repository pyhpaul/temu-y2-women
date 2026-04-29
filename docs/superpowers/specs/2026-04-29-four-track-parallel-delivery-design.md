# Four-Track Parallel Delivery 设计稿

整理日期：2026-04-29

## 1. 目标

当前主线已经具备以下基础能力：

```text
public source refresh
-> signal_ingestion
-> draft_elements / draft_strategy_hints
-> review / promotion
-> active evidence
```

以及：

```text
concept generation
-> prompt bundle
-> image render workflow
-> factory spec draft
```

下一阶段不再围绕“补旧链路缺口”展开，而是进入 **四线并行交付**：

1. **A 线：商品图输入 -> 结构化热点元素抽取**
2. **B 线：公开源元素库扩展 / 日级刷新**
3. **C 线：生产草案元数据增强**
4. **D 线：6 图一致性验证 / 调参**

目标不是一次性做成一个巨型 change，而是把可独立推进的能力拆成边界清晰、可多 agent 并行的四条线，并明确：

- 每条线的职责
- 每条线的文件 ownership
- 哪些 contract 冻结
- merge 顺序
- worktree / branch 策略

## 2. 范围

### 2.1 包含

1. 定义四条并行线的职责边界
2. 定义共享 contract 的冻结范围
3. 定义每条线的主要代码写入范围
4. 定义多 agent 并行的推荐拆法
5. 定义分支 / worktree / PR 顺序

### 2.2 不包含

1. 直接实现任一条线的功能
2. 改造已稳定的 refresh / promotion 主链 contract
3. 在同一 change 中同时重写 image generation 主链
4. 在本设计中决定所有生产细节字段的最终 schema

## 3. 关键设计决定

### 3.1 本轮按“3 条功能线 + 1 条验证线”执行

虽然是四线并行，但只有前三条是主功能交付：

- A：新增输入源（商品图）
- B：扩新增量供给（公开源）
- C：增强输出质量（生产草案）

而 D 线明确定位为：

- 验证
- 评估
- prompt / edit 指令调优
- 样例沉淀

**D 线不承担主链 contract 改造。**

### 3.2 共享 contract 本轮冻结

为了让 A / B 可以安全并行，以下 contract 本轮默认冻结：

1. `structured_candidates` 字段名与最小 schema
2. `signal_ingestion` 对 structured candidates 的消费入口
3. `draft_elements.json` / `draft_strategy_hints.json` 结构
4. `promotion-review-v1` review schema
5. `review -> apply` promotion 主链

如果后续发现这些 contract 必须修改，应单独拆成小 change，而不是混入 A / B / C / D 任一功能线。

### 3.3 slot taxonomy 本轮默认冻结

A 线与 B 线都可能想“顺手加新 slot”。这会引起：

- taxonomy
- ingestion
- promotion
- runtime evidence
- prompt / factory spec

多处同步漂移，直接破坏并行价值。

因此本轮默认：

- **已有 slot 内扩 value：允许**
- **新增 slot：禁止直接混入四线并行**

若确实需要新增 slot，必须先单独开 contract change。

### 3.4 高冲突核心文件尽量单 owner

以下文件是当前主链枢纽：

- `temu_y2_women/signal_ingestion.py`
- `temu_y2_women/public_signal_refresh.py`
- `temu_y2_women/evidence_promotion.py`

并行原则：

- A / B 尽量通过新增模块复用现有入口
- 若必须改核心文件，同一轮只能有一条功能线拥有该文件的写权限

## 4. 四线职责与边界

### 4.1 A 线：商品图输入 -> 结构化热点元素抽取

#### 目标

把用户输入的商品图，转成 objective slot/value 观察结果，并进入现有：

```text
structured candidate
-> draft_elements
-> review / promotion
```

#### 包含

1. 商品图输入 contract
2. 图片观察器 / 观察结果标准化
3. 与现有 structured candidate contract 对接
4. 针对单图或多图商品输入的最小链路验证

#### 不包含

1. 主观风格标签自动判断
2. 新增 slot
3. 改写 promotion schema
4. 图片生成工作流改造

#### 推荐写入范围

- 新增 `product_image_*` 模块
- 少量接入 `signal_ingestion.py`
- 新 fixtures / tests

#### 推荐 ownership

- **拥有**：商品图输入解析、图像观察模块
- **只读**：refresh / promotion 主链

### 4.2 B 线：公开源元素库扩展 / 日级刷新

#### 目标

从公开网页持续补充季节、节日、热点、爆款相关元素，并稳定进入 refresh 主链。

#### 包含

1. source registry 扩展
2. adapter 扩展
3. 多源公开信号 refresh
4. 手动触发与日级刷新入口

#### 不包含

1. 商品图输入
2. 生产草案字段增强
3. 图片生成主链改造
4. review schema 改造

#### 推荐写入范围

- `public_source_registry.py`
- `public_source_adapter.py`
- `public_source_adapters/*`
- `public_signal_refresh.py`
- 对应 tests / fixtures

#### 推荐 ownership

- **拥有**：公开源接入层
- **避免碰**：`factory_spec_builder.py`、`image_generation_*`

### 4.3 C 线：生产草案元数据增强

#### 目标

在当前 concept 与 selected elements 基础上，补出更完整的生产草案元数据，但仍然明确为 **draft**，不是工厂直出文件。

#### 包含

1. 面料方向草案
2. 工艺 / 缝制关注点草案
3. 尺寸 / fit review cues 草案
4. 商业可读性与 sample review cues 增强

#### 不包含

1. 真正可直接下单的工艺单
2. 自动放码
3. 改 refresh / ingestion contract
4. 图片生成逻辑改造

#### 推荐写入范围

- `factory_spec_builder.py`
- `tests/test_factory_spec_builder.py`
- 必要时少量 `prompt_renderer.py` 读取增强，但不建议在首轮引入

#### 推荐 ownership

- **拥有**：生产草案输出层
- **不碰**：refresh / promotion 核心链路

### 4.4 D 线：6 图一致性验证 / 调参

#### 目标

在现有 anchor/edit 主链已经存在的前提下，持续验证真实效果，并沉淀最有效的编辑指令与样例。

#### 包含

1. smoke test
2. 一致性对比样例
3. prompt / edit instruction 微调
4. 失败 case 归档
5. 真实网关调用验证

#### 不包含

1. 改 render job contract
2. 改 `ImageRenderInput` schema
3. 新 provider contract
4. 新一轮图片工作流架构重写

#### 推荐写入范围

- smoke / helper scripts
- `prompt_renderer.py` 中 edit instruction 轻量调优
- `image_generation_openai.py` / `image_generation_workflow.py` 仅做 bugfix 级修正
- 验证文档与结果沉淀

#### 推荐 ownership

- **拥有**：验证脚本、样例对比
- **谨慎改**：`prompt_renderer.py`
- **默认不改**：contract 级图片主链

## 5. 文件 ownership 建议

### A 线 owner

- 新增：`temu_y2_women/product_image_*`
- 可改：`tests/test_signal_ingestion.py`
- 可改：新增与商品图相关 tests / fixtures
- 谨慎共享：`temu_y2_women/signal_ingestion.py`

### B 线 owner

- `temu_y2_women/public_source_registry.py`
- `temu_y2_women/public_source_adapter.py`
- `temu_y2_women/public_source_adapters/*`
- `temu_y2_women/public_signal_refresh.py`
- `tests/test_public_signal_refresh.py`
- 公开源相关 fixtures

### C 线 owner

- `temu_y2_women/factory_spec_builder.py`
- `tests/test_factory_spec_builder.py`

### D 线 owner

- `temu_y2_women/prompt_renderer.py`（仅调优级）
- `temu_y2_women/image_generation_openai.py`（仅 bugfix / smoke 支撑）
- `temu_y2_women/image_generation_workflow.py`（仅 bugfix / smoke 支撑）
- `tests/test_image_generation_*`
- smoke artifacts / docs

## 6. 多 agent 并行推荐

### 推荐 agent 编排

1. **Agent A**
   - 负责商品图输入抽取主线
2. **Agent B**
   - 负责公开源扩元素库
3. **Agent C**
   - 负责生产草案增强
4. **Agent D**
   - 负责 6 图一致性验证与调参

### 不建议的并行方式

1. A / B 同时大改 `signal_ingestion.py`
2. A / B / C 同时改 taxonomy
3. D 把验证线扩成图片主链重构

## 7. worktree / branch 策略

### 推荐 worktree

```text
.worktrees/main-clean
.worktrees/product-image-structured-signal
.worktrees/public-source-expansion
.worktrees/factory-spec-metadata-draft
.worktrees/image-consistency-validation
```

### 推荐 branch

```text
codex/product-image-structured-signal
codex/public-source-expansion
codex/factory-spec-metadata-draft
codex/image-consistency-validation
```

### 原则

1. 每条线独立 worktree
2. 每条线独立 PR
3. 不在脏主仓上切换
4. merge 后及时清理无效 worktree

## 8. merge 顺序

### 第一优先级

- C 线
- D 线

原因：

- C 基本独立
- D 是验证线，不应阻塞主功能线

### 第二优先级

- A / B 谁先成熟谁先合并

但前提是：

- 没有引入 slot taxonomy 变更
- 没有改 shared contract

### 推荐合并顺序

```text
C
-> D
-> A 或 B
-> 另一条 A/B
```

## 9. 完成标准

本设计完成后，应能作为下一步四线落地的统一边界说明，满足：

1. 四条线职责清楚
2. 共享 contract 冻结范围明确
3. 高冲突文件 ownership 明确
4. worktree / branch / PR 策略明确
5. merge 顺序明确
6. 可以直接进入每条线各自的 spec / plan / implementation cycle

## 10. 下一步

在本设计确认后，下一步应：

1. 先为 **A 线：商品图输入 -> 结构化热点元素抽取** 单独起 spec
2. 同时为 B / C / D 准备各自的轻量 spec
3. 再根据每条线的复杂度决定是否立刻分派子 agent 实现
