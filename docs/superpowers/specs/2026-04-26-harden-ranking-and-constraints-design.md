# Harden Ranking and Constraints 设计稿

整理日期：2026-04-26

## 1. 背景

当前 `dress` 主链已经具备：

- request normalize
- strategy select
- evidence retrieval
- composition
- prompt render
- result packaging

同时离线 evidence store 和 signal ingestion pipeline 也已经落地，系统现在的主要短板不再是“能不能跑通”，而是“组合结果是否足够合理”。

当前 `temu_y2_women/composition_engine.py` 仍然采用偏贪心的组合策略：

- 必选 slot：`silhouette`、`fabric` 直接取局部最高分
- 可选 slot：`neckline`、`sleeve`、`pattern`、`detail` 也直接取局部最高分
- `must_have_tags` 在选完之后再校验

这会带来一个已经被用户明确指出的问题：

> 元素单看都高分，但放在一起会风格打架。

当前阶段用户给出的优先修复点是：

- 先处理 `pattern ↔ detail`
- 采用混合策略：
  - 强冲突：禁配
  - 弱冲突：降分
- 第一版可以接受显式规则表，不要求通用风格推断系统

---

## 2. 目标

这条 change `harden-ranking-and-constraints` 的第一阶段目标是：

1. 让 `pattern` 与 `detail` 的组合不再只看各自局部分数，而要看整体兼容性
2. 把“强冲突禁配、弱冲突降分”变成显式、可测试、可追溯的运行时规则
3. 保持现有 request/result contract 不变
4. 为未来扩展到更多 slot pair 建立统一兼容性评估结构，而不是继续往组合器里堆补丁

---

## 3. 非目标

这条 change 第一阶段明确不做：

- 学习型排序
- 通用风格 embedding / 相似度模型
- 多 slot 全局求解器
- 新外部依赖
- Prompt contract 变更
- CLI contract 变更
- 一次性扩到 `fabric ↔ pattern`、`silhouette ↔ neckline` 等其他 pair

---

## 4. 设计原则

### 4.1 明确规则优先于隐式推断

当前问题不是“缺少一个复杂模型”，而是“系统没有显式表达某些组合不合理”。  
第一版应优先把冲突规则写成数据，而不是引入主观、难测的通用风格推断。

### 4.2 兼容性评估集中管理

不能把 `pattern/detail` 的冲突逻辑散写在 `composition_engine.py` 各处。  
应该引入一个中央兼容性评估层，让：

- 规则加载
- 强冲突判断
- 弱冲突扣分
- 解释性 notes

都由统一模块负责。

### 4.3 只对局部高风险组合做有限搜索

当前用户最关心的是 `pattern ↔ detail`。  
因此第一版不需要重写整套 composition solver，只需要：

- 保持必选 slot 现状
- 保持大部分 optional slot 现状
- 仅对 `pattern/detail` 做小范围重排

这样可以用最小代价解决最明确的问题。

---

## 5. 方案选择

### 5.1 备选方案

#### 方案 A：直接在 `composition_engine.py` 内加 if/else 规则

优点：
- 改动快

缺点：
- 规则会散在组合逻辑里
- 后续扩展到更多 slot pair 会迅速失控

#### 方案 B：显式规则表 + 中央兼容性评估器 + `pattern/detail` 局部重排

优点：
- 当前范围可控
- 可解释性强
- 为未来扩展保留干净接口

缺点：
- 比直接补丁多一层结构

#### 方案 C：先建立通用风格标签体系，再做整体一致性评分

优点：
- 长期更通用

缺点：
- 当前过早
- 需要先定义新的 taxonomy
- 主观性强、验证成本高

### 5.2 选定方案

本次采用 **方案 B**：

- 文件化显式规则表
- 中央兼容性评估器
- `pattern/detail` 小范围组合搜索

原因：

1. 它直接命中当前用户最关心的问题
2. 它不会把组合器继续演化成补丁堆
3. 它能在不改 contract 的前提下提高结果合理性

---

## 6. 数据设计

新增文件：

`data/mvp/dress/compatibility_rules.json`

建议结构：

```json
{
  "schema_version": "mvp-v1",
  "rules": [
    {
      "left_slot": "pattern",
      "left_value": "floral print",
      "right_slot": "detail",
      "right_value": "smocked bodice",
      "severity": "weak",
      "penalty": 0.08,
      "reason": "pattern and detail both read busy in the current dress direction"
    }
  ]
}
```

### 第一版约束

- 第一版只允许：
  - `left_slot = pattern`
  - `right_slot = detail`
- `severity` 仅允许：
  - `strong`
  - `weak`
- `penalty` 仅对 `weak` 生效
- 所有 `left_value/right_value` 必须引用当前 active evidence 中真实存在的值

如果规则文件引用了不存在的 value，应视为 evidence authoring error，并返回：

- `INVALID_EVIDENCE_STORE`

---

## 7. 模块设计

新增模块建议：

`temu_y2_women/compatibility_evaluator.py`

职责：

1. 加载并校验兼容性规则
2. 根据已选元素评估兼容性
3. 输出统一的兼容性结果，供组合器消费

建议输出结构包含：

- `hard_conflicts`
- `soft_conflicts`
- `compatibility_penalty`
- `compatibility_notes`

其中：

- `hard_conflicts`：当前组合不可接受
- `soft_conflicts`：当前组合可接受，但需降分
- `compatibility_penalty`：总扣分
- `compatibility_notes`：供结果解释使用

---

## 8. 组合逻辑调整

### 8.1 当前逻辑

当前 `composition_engine` 对 `pattern/detail` 没有联动判断。  
这会产生：

- `pattern` 局部 top1
- `detail` 局部 top1
- 但两者放在一起不合理

### 8.2 新逻辑

第一版只对 `pattern/detail` 做局部强化：

1. 必选 slot 保持现状：
   - `silhouette`
   - `fabric`

2. 其他 optional slot 暂时保持现状：
   - `neckline`
   - `sleeve`

3. 对 `pattern/detail`：
   - 各自取 top K 候选，建议 `K = 3`
   - 允许 `None` 作为“不选该 slot”
   - 枚举以下局部组合：
     - `pattern x detail`
     - `pattern x None`
     - `None x detail`
     - `None x None`

4. 每个组合都走兼容性评估：
   - 强冲突：直接淘汰
   - 弱冲突：记录 penalty
   - 无冲突：正常保留

5. 从合法组合中选择组合分最高的方案

---

## 9. 评分设计

### 9.1 组合选择分

第一版建议引入内部使用的 `selection_score`：

```text
selection_score =
  sum(selected element effective_score)
  - compatibility_penalty
```

这个分数只用于组合决策，不要求暴露为新字段。

### 9.2 concept_score

对外的 `concept_score` 字段保持不变，但其计算应与真实选择逻辑对齐：

```text
concept_score =
  (sum(selected effective_score) - compatibility_penalty) / len(selected)
```

这样可以避免“内部靠 penalty 选组合，对外却看不出差异”的不一致。

---

## 10. 强冲突与弱冲突行为

### 10.1 强冲突

若 `pattern + detail` 命中强冲突：

- 该组合直接无效
- 系统优先尝试：
  - 换次优 `detail`
  - 换次优 `pattern`
  - 不选其中一个 optional slot

只有在约束逼迫该组合必须出现且不存在替代时，才应失败。

### 10.2 弱冲突

若命中弱冲突：

- 组合仍然合法
- 但会扣分
- 如果有更协调的替代组合，则应由替代组合胜出

---

## 11. 可解释性输出

本次不改 response schema。  
兼容性解释信息应复用现有结果字段输出，例如写入 `constraint_notes`。

新增 note 示例：

- `style conflict avoided: floral print + smocked bodice`
- `style compatibility penalty applied: floral print + smocked bodice (0.08)`

这样可以在不扩字段的前提下提升可解释性。

---

## 12. 测试设计

至少补以下测试：

1. **无冲突组合**
   - `pattern` 与 `detail` 可同时保留

2. **弱冲突 + 有替代**
   - 系统应优先选更协调的替代组合

3. **弱冲突 + 无替代**
   - 系统可保留该组合，但应体现 penalty

4. **强冲突**
   - 系统不得同选该 `pattern/detail`
   - 应尝试替代或省略其中一个 slot

5. **强冲突与 must-have 发生碰撞**
   - 若唯一满足路径是强冲突组合，应返回 `CONSTRAINT_CONFLICT`

6. **规则文件校验**
   - 若兼容性规则引用不存在的 `pattern/detail` 值，应返回 `INVALID_EVIDENCE_STORE`

---

## 13. 风险与缓解

### 风险 1：规则过少，改善有限

缓解：
- 第一版接受这一点
- 重点是先把机制搭起来，而不是一次覆盖所有审美冲突

### 风险 2：penalty 设得不合理

缓解：
- 第一版使用固定、少量、可测的 penalty
- 通过 fixture 锁定决策结果

### 风险 3：组合器复杂度继续膨胀

缓解：
- 把兼容性判断集中到独立模块
- 只对 `pattern/detail` 做局部搜索，不重写全局求解器

### 风险 4：未来扩展更多 slot pair 时结构被打破

缓解：
- 兼容性评估器从第一版就按可扩展结构设计
- 当前只收一个 pair，但接口不是一次性写死

---

## 14. 实施顺序建议

建议按以下顺序推进：

1. 新增 `compatibility_rules.json`
2. 在 evidence 层加入 compatibility rule 校验
3. 实现 `compatibility_evaluator.py`
4. 调整 `composition_engine.py`，只对 `pattern/detail` 做局部组合搜索
5. 增加回归测试与 fixture

---

## 15. 结论

这条 change 的第一阶段不追求建立完整求解框架，而是用最小、最稳、最可测试的方式解决一个已被明确指出的真实问题：

> `pattern` 与 `detail` 的高分局部最优组合，未必是整体合理组合。

通过“显式规则表 + 中央兼容性评估器 + `pattern/detail` 局部重排”，系统可以在保持现有 contract 稳定的前提下，明显减少风格打架的输出，为后续更完整的 ranking hardening 打下干净基础。
