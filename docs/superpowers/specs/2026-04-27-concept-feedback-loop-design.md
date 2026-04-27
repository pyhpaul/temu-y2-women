# Concept Feedback Loop 设计稿

整理日期：2026-04-27

## 1. 目标

这次 change 的目标不是扩展新模型能力，而是把当前已经跑通的：

```text
signal -> promotion -> active evidence -> concept -> prompt
```

补成一个最小可用闭环：

```text
concept result
-> review
-> feedback ledger
-> apply to active elements
-> next run changes
```

完成后，人工对一套 `dress` 概念结果做 `keep / reject`，就能通过受控流程回写到 `elements.json`，让下一轮生成结果产生可解释偏移。

## 2. 范围

### 包含

1. 从成功的 `dress` 概念结果生成确定性的 feedback review 文件
2. 人工只编辑 `decision` 与 `notes`
3. `apply` 时先做 fail-closed 校验
4. 成功后同时写：
   - `data/mvp/dress/elements.json`
   - `data/feedback/dress/feedback_ledger.json`
   - `feedback_report.json`
5. `keep / reject` 只影响本次概念中已选中的 active elements

### 不包含

- strategy feedback
- 图片满意度反馈
- 打样反馈
- 上架后业务指标
- 运行时动态读取 ledger 叠加分数
- 自动去重或幂等控制

## 3. 工作流

### 3.1 prepare

输入：成功的 concept result JSON

输出：`feedback-review-v1`

review 文件会锁定以下字段：

- `request_normalized`
- `selected_elements`
- `selected_element_ids`
- `concept_score`
- `request_fingerprint`
- `concept_fingerprint`

人工只允许修改：

- `decision`: `keep | reject`
- `notes`

### 3.2 apply

`apply` 会重新从原始 result payload 构造期望 review 模板，然后逐项校验：

1. 输入必须是成功的 `dress` result
2. review 锁定字段必须完全一致
3. `decision` 必须是 `keep` 或 `reject`
4. 目标 `element_id` 必须仍存在于 active evidence

全部通过后才会进入写阶段。

## 4. 分数回写规则

- `keep`：每个目标 element 的 `base_score +0.02`
- `reject`：每个目标 element 的 `base_score -0.02`
- 超出 taxonomy 范围时按边界 clamp

这里故意不做更复杂的权重学习：

- 不区分 slot
- 不区分主次元素
- 不从 notes 反推结构化原因

先把闭环跑通，再看是否需要更细粒度策略。

## 5. 数据结构

### 5.1 Review 文件

建议 shape：

- `schema_version`
- `category`
- `feedback_target`
- `decision`
- `notes`

### 5.2 Ledger

建议路径：

`data/feedback/dress/feedback_ledger.json`

每条 record 至少包含：

- `feedback_id`
- `decision`
- `element_ids`
- `score_delta`
- `request_fingerprint`
- `concept_fingerprint`
- `notes`
- `recorded_at`

### 5.3 Report

建议输出：

- `summary`
- `affected_elements`
- `warnings`

其中 `warnings` 主要用于记录 clamp 发生情况。

## 6. 关键设计决定

### 6.1 采用 review-gated workflow

不直接拿生成结果回写 evidence，而是先生成 review 文件。  
原因是这个仓库现在已经形成了 `prepare/review/apply/report` 的稳定模式，feedback 最好复用这套操作习惯。

### 6.2 保留 ledger，再 apply 到 active evidence

如果只改 `elements.json`，可追溯性太差；  
如果只记 ledger、运行时动态叠加，又会把主链搞复杂。

所以这次采用折中方案：

```text
reviewed feedback
-> append ledger
-> apply delta to active elements
```

### 6.3 保持生成结果 contract 不变

feedback 是 generation 的下游工作流，不应该为了 feedback 把当前成功结果 schema 再扩大一轮。  
这次所有 review 信息都从现有成功 payload 推导。

## 7. 风险

1. **重复对同一概念执行 keep/reject 会叠加影响**  
   当前接受这个行为，不做幂等。

2. **概念级反馈会把一组元素等权处理**  
   这会牺牲精度，但能换来最小闭环。

3. **prepare 和 apply 之间 active evidence 可能发生漂移**  
   通过“目标 element_id 必须存在”做 fail-closed 防守。

## 8. 完成标准

完成后应能稳定验证这条实验路径：

```text
run concept generation
-> prepare feedback review
-> mark keep / reject
-> apply feedback
-> rerun same request
-> observe retrieved/selected elements drift
```

这会是当前项目第一次真正具备“反馈影响下一轮输出”的试验能力。
