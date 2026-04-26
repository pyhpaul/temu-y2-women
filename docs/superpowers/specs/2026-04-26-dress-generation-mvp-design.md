# Dress Generation MVP 与后续 Change 边界设计

整理日期：2026-04-26

## 1. 设计目标

在 `Temu 美区女装爆款生成系统 V2` 总设计的基础上，先拆出一条可以独立实现和验证的第一期 change：

- 当前 change：`dress-generation-mvp`
- 下一条 change：`enrich-dress-evidence-store`

这份文档的目的不是重复 V2 总设计，而是明确：

1. 第一条 change 到底做到哪里算完成
2. 第一条 change 明确不做什么
3. 第二条 change 解决什么问题
4. 两条 change 之间的责任边界和依赖关系

---

## 2. 当前 Change：`dress-generation-mvp`

### 2.1 目标

第一条 change 的目标不是交付完整业务系统，而是跑通 `dress` 单品类的最小可用链路，证明系统主链成立：

```text
request
-> normalize
-> strategy select
-> retrieve elements
-> compose concept
-> render A/B prompt
-> package result
```

成功标准是：输入一条规范请求后，系统可以稳定输出一份可解释结果包；失败时也能返回结构化错误，而不是静默退化。

### 2.2 范围包含

当前 change 包含以下能力：

1. 请求归一化
2. 时效策略选择
3. 本地离线元素读取
4. 候选元素检索与基础过滤
5. 最小组合引擎
6. A/B Prompt 渲染
7. 统一结果包装
8. 基础错误返回
9. 固定样例验证

### 2.3 明确不包含

当前 change 不包含：

- 自动抓取或导入公开信号
- 大规模元素库建设
- 复杂评分体系
- 真实图像生成调用
- 反馈闭环
- 多品类扩展
- 复杂供应链判断
- 完整侵权判断

### 2.4 为什么这样拆

这条 change 要先证明“系统主链是否成立”，而不是同时解决：

- 数据从哪里来
- 数据够不够厚
- 图像模型效果稳不稳
- 多品类是否可扩展

第一条 change 必须尽量压缩依赖，避免一开始把抓取、抽取、评分、出图、反馈全部耦合进来，导致问题不可定位。

---

## 3. MVP 输入 / 输出契约

### 3.1 输入契约

第一版请求对象收敛为：

**必填**
- `category`：固定为 `dress`
- `target_market`：默认 `US`
- `target_launch_date`：`YYYY-MM-DD`
- `mode`：`A | B`

**可选**
- `price_band`
- `occasion_tags`
- `must_have_tags`
- `avoid_tags`

示例：

```json
{
  "category": "dress",
  "target_market": "US",
  "target_launch_date": "2026-06-15",
  "mode": "B",
  "price_band": "mid",
  "occasion_tags": ["vacation"],
  "must_have_tags": ["floral"],
  "avoid_tags": ["bodycon"]
}
```

### 3.2 输出契约

MVP 输出不是单条 prompt，而是一份可解释结果包：

- `request_normalized`
- `selected_strategies`
- `retrieved_elements`
- `composed_concept`
- `prompt_bundle`
- `warnings`

示例结构：

```json
{
  "request_normalized": {},
  "selected_strategies": [],
  "retrieved_elements": [],
  "composed_concept": {},
  "prompt_bundle": {
    "mode": "B",
    "prompt": "...",
    "render_notes": [],
    "development_notes": []
  },
  "warnings": []
}
```

### 3.3 失败返回

失败必须结构化、可解释。第一版至少覆盖：

- `UNSUPPORTED_CATEGORY`
- `INVALID_REQUEST`
- `INVALID_DATE`
- `NO_STRATEGY_MATCH`
- `NO_CANDIDATES`
- `CONSTRAINT_CONFLICT`
- `INCOMPLETE_CONCEPT`

示例：

```json
{
  "error": {
    "code": "NO_CANDIDATES",
    "message": "no eligible dress elements found after filtering",
    "details": {
      "category": "dress",
      "avoid_tags": ["bodycon"]
    }
  }
}
```

---

## 4. MVP 数据结构

### 4.1 第一版不用数据库

第一版不引入 DB，直接使用本地结构化文件：

```text
data/mvp/dress/elements.json
data/mvp/dress/strategy_templates.json
```

原因：

- 当前目标是主链验证，不是数据平台建设
- 文件仓便于人工维护与审查
- 后续迁移到 SQLite / Postgres 的成本可控

### 4.2 `elements.json` 最小 Schema

元素是“可组合的商品元素”，不是完整商品。

示例：

```json
{
  "element_id": "dress-silhouette-a-line-001",
  "category": "dress",
  "slot": "silhouette",
  "value": "a-line",
  "tags": ["feminine", "summer", "vacation"],
  "base_score": 0.78,
  "price_bands": ["mid"],
  "occasion_tags": ["vacation", "casual"],
  "season_tags": ["spring", "summer"],
  "risk_flags": ["common_market_pattern"],
  "evidence_summary": "frequent in lightweight summer dresses",
  "status": "active"
}
```

最小 slot 集合建议为：

- `silhouette`
- `fabric`
- `neckline`
- `sleeve`
- `pattern`
- `detail`

### 4.3 `strategy_templates.json` 最小 Schema

时效策略模板负责把上架时间和场景偏好转换成可执行加权规则。

示例：

```json
{
  "strategy_id": "summer-vacation-dress",
  "category": "dress",
  "target_market": "US",
  "priority": 10,
  "date_window": {
    "start": "05-15",
    "end": "08-31"
  },
  "occasion_tags": ["vacation", "casual"],
  "boost_tags": ["summer", "lightweight", "floral", "resort"],
  "suppress_tags": ["heavy", "velvet", "holiday"],
  "slot_preferences": {
    "silhouette": ["a-line", "fit-and-flare"],
    "fabric": ["lightweight woven", "cotton poplin"],
    "pattern": ["floral", "tropical"]
  },
  "score_boost": 0.12,
  "score_cap": 0.2,
  "prompt_hints": [
    "fresh summer styling",
    "lightweight fabric feel",
    "vacation-ready feminine silhouette"
  ],
  "reason_template": "launch date falls into the US summer vacation window",
  "status": "active"
}
```

模板选择规则：

1. 按 `category + target_market` 过滤
2. 用 `target_launch_date` 匹配 `date_window`
3. 如果请求里带 `occasion_tags`，优先选择有交集的模板
4. 最多选择 2 个模板
5. 多模板默认等权合并
6. 总策略加权受 `score_cap` 约束

---

## 5. 组合引擎与 Prompt 渲染

### 5.1 组合引擎

第一版采用按 slot 顺序的贪心组合，而不做复杂搜索或回溯求解。

slot 分级：

**必选**
- `silhouette`
- `fabric`

**强建议**
- `neckline`
- `sleeve`

**可选**
- `pattern`
- `detail`

候选有效分数公式：

```text
effective_score =
  base_score
  + strategy_boost
  + request_match_bonus
  - risk_penalty
```

最小硬规则：

- 命中 `avoid_tags` 的元素直接排除
- `must_have_tags` 至少命中一次，否则失败
- 明显季节冲突元素在强时效策略下剔除
- 同一 slot 只选一个值
- 已知冲突组合时回退次高分候选

### 5.2 `composed_concept` 结构

组合结果输出为结构化对象，而不是自然语言拼接：

```json
{
  "category": "dress",
  "concept_score": 0.84,
  "selected_elements": {
    "silhouette": {
      "element_id": "dress-silhouette-a-line-001",
      "value": "a-line"
    },
    "fabric": {
      "element_id": "dress-fabric-cotton-poplin-001",
      "value": "cotton poplin"
    }
  },
  "style_summary": [
    "summer-ready",
    "vacation-oriented",
    "feminine silhouette",
    "lightweight feel"
  ],
  "constraint_notes": [
    "must_have_tags satisfied: floral",
    "avoid_tags removed: bodycon"
  ]
}
```

### 5.3 A/B Prompt 渲染

Prompt 渲染器只消费：

- `mode`
- `composed_concept`
- `selected_strategies`
- `warnings`

统一使用以下段落块：

```text
[商品主体]
[核心结构]
[风格与时效]
[展示方式]
[约束与避免项]
```

模式差异：

- **A 模式**：商品灵感图 / 概念图，强调整体风格和商品吸引力
- **B 模式**：设计说明图 / 开发参考图，强调版型、领型、袖型、面料和细节

---

## 6. 模块划分与运行形态

第一版采用 `library-first, CLI-first`：

- 核心逻辑做成可调用模块
- 先提供最小 CLI 入口
- 暂不服务化

建议模块：

1. `request_normalizer`
2. `strategy_selector`
3. `element_repository`
4. `composition_engine`
5. `prompt_renderer`
6. `result_packager`
7. `generate_dress_concept`

最小运行形态：

```text
generate-dress-concept --input request.json
```

输出标准 JSON 到 stdout 或文件。

---

## 7. 验证方式

第一版的验证重点不是图像效果，而是主链稳定性、输出可解释性和约束是否生效。

### 7.1 单元验证

- 请求校验
- 日期解析
- 策略选择
- slot 分组与组合
- Prompt 渲染

### 7.2 集成验证

至少准备以下固定样例：

1. 夏季度假风 A 模式
2. 夏季度假风 B 模式
3. `must_have_tags` 命中案例
4. `avoid_tags` 触发过滤案例
5. 约束冲突失败案例

### 7.3 输出快照验证

对结果包做 snapshot / golden file 对比，重点验证：

- 命中策略是否稳定
- `composed_concept` 是否完整
- prompt 是否包含关键结构字段
- warning / error 是否正确

### 7.4 不把真实出图设为阻塞项

当前 change 不要求真实图像模型调用打通。第一版完成条件是稳定输出 `prompt_bundle`，将“生成逻辑正确”和“模型效果波动”解耦。

---

## 8. 下一条 Change：`enrich-dress-evidence-store`

### 8.1 目标

第二条 change 的目标不是扩展主链功能，而是把 MVP 依赖的演示级手工数据升级成更像真实业务资产的 `dress` 离线证据仓。

### 8.2 范围包含

- 扩充 `dress` 元素样本数量和覆盖度
- 固化 `slot / tag / risk` 字典规范
- 提升 `evidence_summary` 和基础分的可维护性
- 增加元素数据校验规则
- 清理重复、冲突、低质量样本

### 8.3 明确不包含

- 自动网页抓取
- 自动元素抽取流水线
- 真实图像生成接入
- 反馈回写
- 多品类扩展

### 8.4 完成定义

完成后应达到：

- `dress` 离线仓不再只是演示级样本
- 同一请求在多组样例下结果更稳定
- 后续评分强化、信号接入可以直接挂在这个仓上

### 8.5 与当前 Change 的边界

两条 change 的边界必须保持明确：

- `dress-generation-mvp` 解决的是：**系统主链是否成立**
- `enrich-dress-evidence-store` 解决的是：**主链依赖的数据是否足够稳**

第一条先证明“会跑”，第二条再解决“跑得稳不稳”。

---

## 9. 后续 Change 路线

推荐顺序：

1. `dress-generation-mvp`
2. `enrich-dress-evidence-store`
3. `add-signal-ingestion-pipeline`
4. `harden-ranking-and-constraints`
5. `integrate-image-generation-output`
6. `add-feedback-loop-and-evaluation`
7. `expand-category-beyond-dress`

这个顺序的核心原则是：

1. 先验证主链
2. 再增强离线仓
3. 再接信号来源
4. 再强化排序与约束
5. 再接真实出图
6. 再做反馈闭环
7. 最后横向扩展到多品类

---

## 10. 结论

当前阶段已经把第一条 change 和第二条 change 的边界固定下来：

- 当前 change 的目标是 `dress` 单品类最小可用主链
- 下一条 change 的目标是 `dress` 离线证据仓增强

只要严格按这两个边界推进，后续实现时就不需要在“现在到底是在修主链，还是在补数据能力”之间反复摇摆。
