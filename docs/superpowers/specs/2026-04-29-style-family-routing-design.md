# Style Family Routing 设计稿

整理日期：2026-04-29

## 1. 目标

当前主线已经具备：

- `request -> strategy -> candidate retrieval -> composition -> prompt bundle`
- `hero_front generate + derived edit-only` 的图片生成链路
- 可运行的最小女装概念与图片产物框架

但当前风格变化仍然停留在：

- 同一骨架下的局部元素变动
- 例如 `floral print -> polka dot`
- 很难形成“一眼可分”的风格族群差异

本次 change 的目标，是在现有概念生成链路中加入一层 **style family routing**，让系统先决定“属于哪一类风格族群”，再在该族群内挑选元素与渲染 prompt，从而把当前输出从“元素扰动”提升到“族群级分化”。

第一阶段只要求：

1. 支持显式 `style_family` override
2. 不传时支持自动默认回退
3. 先落 4 个风格族群
4. 先用 4 张 `hero_front` anchor 图验证差异是否真正拉开

## 2. 范围

### 2.1 包含

1. 请求结构新增可选 `style_family`
2. 新增 `style_families.json` 运行时配置
3. 新增 style family 解析与选择模块
4. 让 candidate retrieval 支持族群级硬约束与软偏置
5. 让 prompt 渲染支持族群级视觉外壳
6. 扩充能支撑 4 个族群分化的元素库
7. 在结果与 factory spec 中暴露 `selected_style_family`
8. 生成 4 张 anchor 主图做人工验收

### 2.2 不包含

1. 本轮不解决 6 图 edit 一致性问题
2. 不把 style family 直接混入 existing strategy template 语义
3. 不引入新的 promotion / ingestion contract
4. 不做完全由公开信号驱动的复杂 style clustering
5. 不做工厂直出级 tech pack

## 3. 关键设计决定

### 3.1 style family 独立于 strategy template

现有 `strategy_templates` 负责的是：

- 市场
- 季节
- 时间窗口
- occasion 粗粒度偏置

本次新增的 `style family` 负责的是：

- 视觉骨架
- 关键轮廓
- 表面方向
- 场景/构图/造型语法

二者是不同维度：

- strategy 更偏“商业时间与市场上下文”
- style family 更偏“风格 archetype”

因此本轮不把 family 硬塞进 `strategy_templates.json`，避免后续出现语义缠绕。

### 3.2 style family 不是纯加分，而是“硬约束 + 软偏置”

如果只是继续在现有检索分数上加一点 boost，系统仍然会收敛到：

- `a-line`
- `cotton poplin`
- `mini`
- `drop waist`
- `white`

这类当前的高分母版。

因此 family 需要两层控制：

#### 第一层：硬约束

优先约束关键骨架 slot：

- `silhouette`
- `fabric`
- `dress_length`
- `waistline`
- `color_family`

必要时也可约束：

- `pattern`
- `detail`

#### 第二层：软偏置

对其他可变化 slot 加权：

- `neckline`
- `sleeve`
- `print_scale`
- `opacity_level`

这样既能保证大方向拉开，也不至于每次生成完全僵硬。

### 3.3 先显式 override，再自动回退

为了快速验证风格拉开效果，本轮优先支持：

- 请求显式传入 `style_family`

同时保留：

- 不传时按 heuristics 自动选择

这样可以兼顾两件事：

1. 当前阶段快速做强对照实验
2. 后续仍可回到自动流程

### 3.4 自动选择先走简单 heuristic，不追求复杂智能

第一阶段自动逻辑保持简单、可预测：

- `party` -> `party-fitted`
- `vacation` / `resort` -> `vacation-romantic`
- `must_have_tags` 含 `transitional` 或非度假 `casual` -> `clean-minimal`
- 其余 -> `city-polished`

这不是最终智能路由，只是第一阶段最小可用默认值。

### 3.5 Prompt 外壳必须同步分化

只改元素，不改 prompt 外壳，图仍然容易像同一个拍摄模板。

因此每个 style family 必须同步控制：

- 主图主体描述
- 场景
- 光线
- pose / styling
- 商业化语气
- avoid 项

否则只能得到“同一套 studio 提示词 + 不同印花”。

## 4. 第一阶段 4 个 style family

### 4.1 vacation-romantic

视觉目标：

- 轻盈、柔和、女性化、度假感

核心方向：

- a-line / soft volume
- floral 或轻表面纹理
- airy fabric
- 更柔和的光线与 resort 场景

### 4.2 clean-minimal

视觉目标：

- 克制、干净、低噪音、无明显装饰

核心方向：

- solid / no pattern
- opaque
- clean seam lines
- quieter palette
- 更干净的 studio / product hero 语法

### 4.3 city-polished

视觉目标：

- 利落、成熟、都市感、可通勤可轻商务

核心方向：

- structured fabric
- more polished neckline/sleeve choices
- solid or restrained surface
- neutral or dark color story
- 更明确的 urban commercial polish

### 4.4 party-fitted

视觉目标：

- 更贴身、更夜场、更高对比、更显线条

核心方向：

- bodycon
- shorter length
- fitted or stretch fabric
- bold color or sleek neutral
- stronger evening / nightlife presentation

## 5. 数据结构设计

### 5.1 请求结构

`NormalizedRequest` 新增：

- `style_family: str | None`

行为：

- 未提供：`None`
- 显式提供：按 `style_families.json` 校验是否支持

### 5.2 新增运行时配置文件

新增：

- `data/mvp/dress/style_families.json`

每条记录至少包含：

- `style_family_id`
- `status`
- `selection_mode`
- `hard_slot_values`
- `soft_slot_values`
- `blocked_slot_values`
- `prompt_shell`
- `fallback_reason`

其中：

- `hard_slot_values`
  - slot -> 允许值列表
- `soft_slot_values`
  - slot -> 偏好值列表
- `blocked_slot_values`
  - slot -> 禁止值列表
- `prompt_shell`
  - 该 family 对主图提示词的视觉外壳

### 5.3 结果结构

最终 success result 中新增：

- `selected_style_family`

建议形状：

```json
{
  "style_family_id": "clean-minimal",
  "selection_mode": "explicit",
  "reason": "request explicitly requested style_family=clean-minimal"
}
```

### 5.4 factory spec

`factory_spec.known` 中新增：

- `selected_style_family_id`

便于后续生产草案和人工 review 直接知道本次概念属于哪条族群路线。

## 6. 模块与责任边界

### 6.1 新增模块

- `temu_y2_women/style_family_repository.py`
  - 读取/校验 `style_families.json`
- `temu_y2_women/style_family_selector.py`
  - 显式选择 + 自动回退

### 6.2 修改模块

#### `temu_y2_women/models.py`

- 扩 `NormalizedRequest`
- 增加 style family 相关 dataclass

#### `temu_y2_women/request_normalizer.py`

- 解析并校验可选 `style_family`

#### `temu_y2_women/evidence_repository.py`

- `retrieve_candidates` 接入 style family
- family 先做 hard filter，再做 soft boost

#### `temu_y2_women/orchestrator.py`

- 加载 style family runtime config
- 解析 selected style family
- 在下游 result / prompt / factory spec 之间传递

#### `temu_y2_women/prompt_renderer.py`

- family-specific subject / scene / lighting / pose / styling shell

#### `temu_y2_women/result_packager.py`

- 输出 `selected_style_family`

#### `temu_y2_women/factory_spec_builder.py`

- known / inferred 区域补 family 语义

## 7. 候选检索与组合规则

### 7.1 family hard filter

对每个 element candidate：

1. 若其 slot 在 `blocked_slot_values` 中且 value 命中，直接排除
2. 若其 slot 在 `hard_slot_values` 中且 value 不在允许列表，直接排除
3. 其余候选继续进入现有 request/strategy 过滤链路

### 7.2 family soft boost

在现有 `effective_score` 计算上，若候选 value 命中 family `soft_slot_values`：

- 给予额外 boost

但 boost 不应大到能推翻显式 avoid/blocked 规则。

### 7.3 family 与 request 约束冲突

若显式 `style_family` 与请求自身约束冲突，例如：

- `style_family=party-fitted`
- `avoid_tags=["bodycon"]`

则优先 fail closed，返回结构化冲突错误，而不是偷偷改成别的 family。

### 7.4 family 与 existing strategy 并存

顺序为：

1. request normalize
2. strategy select
3. style family select
4. candidate retrieval with strategy + style family
5. composition
6. prompt / factory spec

即：

- strategy 不被 family 替代
- family 在 candidate retrieval 与 prompt rendering 阶段增强当前概念路径

## 8. Prompt 渲染策略

每个 family 至少影响以下行：

- `[商品主体]`
- `[核心结构]`
- `[生产与细节展示要求]`
- `[镜头与构图]`
- `[场景与光线]`
- `[约束与避免项]`

第一阶段的关键要求不是文学化，而是：

- 让图像模型明确感知“这是不同 archetype”

例如：

- `clean-minimal`
  - 减少 pattern/detail 噪音
  - 更中性、更克制的场景
- `party-fitted`
  - 更明确的 fitted silhouette
  - 更高对比、更夜间/晚场商业语义

## 9. 元素库扩充策略

为支持 4 条 style family，必须补充足以拉开差异的新元素。

优先补这些 slot：

- `fabric`
- `neckline`
- `sleeve`
- `dress_length`
- `color_family`
- `detail`

其中 `party-fitted` 和 `clean-minimal` 需要优先补：

- fitted / sleek 方向
- solid / minimal 方向

否则 family 层即使存在，最后仍会退回旧母版。

## 10. 错误处理

### 10.1 style family 配置错误

若 `style_families.json`：

- 缺字段
- slot 非法
- 引用了不存在的 active values

则报：

- `INVALID_STYLE_FAMILY_CONFIG`

### 10.2 请求错误

若请求显式传入不支持的 `style_family`：

- `INVALID_REQUEST`

### 10.3 显式 family 约束冲突

若显式 family 与请求约束冲突，导致骨架无法满足：

- `CONSTRAINT_CONFLICT`

且 details 里应说明：

- `style_family`
- 冲突字段
- 冲突值

## 11. 测试策略

### 11.1 请求与配置

覆盖：

- request 接受 `style_family`
- request 拒绝未知 `style_family`
- style family config loader 拒绝非法 slot/value

### 11.2 候选检索

覆盖：

- hard filter 生效
- blocked value 生效
- soft boost 生效
- 显式 `party-fitted + avoid bodycon` fail closed

### 11.3 Prompt 渲染

覆盖：

- 4 个 family 的 prompt shell 差异
- 关键视觉语义正确出现

### 11.4 Orchestrator

覆盖：

- success result 输出 `selected_style_family`
- factory spec 输出 `selected_style_family_id`
- 代表性 family 请求能选出明显不同骨架

## 12. 验收标准

本轮真正的验收不是“单测都绿”，而是：

1. 单测与验证脚本通过
2. 4 个 style family 的 `hero_front` anchor 主图可生成
3. 不看 prompt 文本，只看图，也能判断：
   - 不是同一条裙子的局部改款
   - 属于 4 条明显不同的风格路线

若做不到第 3 条，就说明本次 change 还没真正达标。
