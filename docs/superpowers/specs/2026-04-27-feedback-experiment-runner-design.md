# Feedback Experiment Runner 设计稿

整理日期：2026-04-27

## 1. 目标

这次 change 不扩展新的反馈语义，而是把当前已经具备的：

```text
generation
-> feedback review
-> feedback apply
```

补成一条可重复、可观察、默认不污染主数据的离线实验路径：

```text
baseline generation
-> prepare feedback review
-> mark keep / reject
-> apply feedback into isolated workspace
-> rerun same request
-> compare before / after
```

完成后，仓库应能稳定回答一个更关键的问题：  
**一次概念级 `keep / reject` 反馈，是否真的会影响下一轮同请求的检索、选中元素或概念结果。**

## 2. 范围

### 包含

1. 新增一个面向实验的离线 runner 工作流
2. 在实验开始时复制 active evidence / taxonomy / ledger 到独立 workspace
3. 在 workspace 副本上执行 baseline generation、feedback prepare、feedback apply、rerun generation
4. 产出确定性的 manifest / report / before-after result 文件
5. 为 generation 主链增加可选 evidence path overrides，使其能读取 workspace 副本而不是固定主数据路径

### 不包含

- 新的 feedback 决策类型
- strategy feedback
- feedback 幂等 / 去重规则
- 批量实验调度
- Web UI 或可视化页面
- 对默认生产路径做隐式数据改写

## 3. 设计选型

### 3.1 方案对比

#### 方案 A：直接在主数据上执行一轮完整实验

- 优点：实现最短
- 缺点：污染 `data/mvp/dress/*`，实验不可安全重跑，也不利于对比

#### 方案 B：只做一个 diff 工具，不负责实验执行

- 优点：侵入最小
- 缺点：用户仍要手工拼接 generation / feedback / rerun，多步实验容易出错

#### 方案 C：workspace 隔离的 experiment runner（采用）

- 优点：
  - 默认不污染主数据
  - 一次实验的输入、过程、输出都能落盘
  - 能直接验证“feedback 是否影响下一轮结果”
- 代价：
  - 需要给 generation 主链补一层路径注入能力

### 3.2 采用结论

采用 **workspace 隔离的 experiment runner**。  
实验 runner 是 orchestration 层能力，不改变现有 feedback contract，只把已有能力按实验顺序稳定串起来。

## 4. 工作流

### 4.1 prepare

输入：

- request JSON
- experiment root directory
- 可选：workspace 名称

行为：

1. 校验 request 可用于 `dress` generation
2. 在 experiment root 下创建新的 workspace 目录
3. 复制以下文件到 workspace：
   - `elements.json`
   - `strategy_templates.json`
   - `evidence_taxonomy.json`
   - `feedback_ledger.json`
4. 用 workspace 副本执行 baseline generation
5. 从 baseline result 生成 feedback review 模板
6. 写出 experiment manifest

输出文件建议为：

- `workspace/baseline_result.json`
- `workspace/feedback_review.json`
- `workspace/experiment_manifest.json`
- `workspace/data/...` 下的 evidence 副本

### 4.2 apply

输入：

- reviewed feedback JSON
- experiment manifest JSON

行为：

1. 从 manifest 读取 request、workspace 路径、基线结果路径、evidence 副本路径
2. 仅在 workspace 副本上执行 feedback apply
3. 用同一个 request、同一份 workspace evidence 副本再次执行 generation
4. 对 baseline 与 rerun 结果做结构化对比
5. 写出实验报告

输出文件建议为：

- `workspace/post_apply_result.json`
- `workspace/feedback_report.json`
- `workspace/experiment_report.json`

## 5. 关键模块边界

### 5.1 Evidence path configuration

当前 generation 主链固定从：

- `data/mvp/dress/elements.json`
- `data/mvp/dress/strategy_templates.json`
- `data/mvp/dress/evidence_taxonomy.json`

读取 active evidence。  
这次需要补一个小的路径配置对象，例如：

- `elements_path`
- `strategies_path`
- `taxonomy_path`

要求：

- 默认行为保持不变
- 仅在显式传入 overrides 时读取 workspace 副本
- 不把路径参数散落到多个内部函数签名里

### 5.2 Experiment runner module

新增独立模块承接实验 orchestration，负责：

- workspace 初始化
- baseline generation
- review template prepare
- feedback apply
- rerun generation
- before/after diff report

它不重新实现 generation 或 feedback 逻辑，只组合现有稳定接口。

### 5.3 Experiment CLI

新增独立 CLI，保持和已有 `signal_ingestion_cli.py`、`evidence_promotion_cli.py`、`feedback_loop_cli.py` 一致的风格：

- `prepare`
- `apply`

CLI 只负责参数解析、调用 runner、输出 JSON。

## 6. 数据结构

### 6.1 experiment manifest

建议 schema：

- `schema_version`
- `experiment_id`
- `category`
- `request_path`
- `request_fingerprint`
- `workspace_root`
- `baseline_result_path`
- `feedback_review_path`
- `active_elements_path`
- `active_strategies_path`
- `taxonomy_path`
- `ledger_path`
- `created_at`

manifest 的职责是把一次实验固定成可重放对象，避免 apply 阶段重新猜路径。

### 6.2 experiment report

建议 schema：

- `schema_version`
- `experiment_id`
- `decision`
- `baseline_summary`
- `rerun_summary`
- `score_deltas`
- `selected_element_changes`
- `retrieval_rank_changes`
- `warnings`

其中：

- `baseline_summary` / `rerun_summary` 至少包含 `concept_score` 与 `selected_elements`
- `score_deltas` 记录 feedback apply 实际改动的 `base_score`
- `selected_element_changes` 记录 slot 级 before/after
- `retrieval_rank_changes` 记录候选排名是否漂移

## 7. diff 规则

本次实验报告不追求通用 diff 引擎，只回答实验是否生效。

最小比较集合：

1. `concept_score` before / after
2. `selected_elements` before / after
3. `retrieved_elements` 中相关 element 的排名或有效分数变化
4. feedback 目标 element 的 `base_score` 变化

报告应能明确区分三种结果：

- **selection_changed**：已选元素发生变化
- **retrieval_changed_only**：候选排序或分数变了，但最终选中未变
- **no_observable_change**：本轮反馈未造成可见漂移

## 8. 错误处理

runner 应保持和现有工作流一致的 fail-closed 策略：

1. prepare 任一步失败时，不写不完整 manifest
2. apply 只允许操作 manifest 指向的 workspace 副本
3. reviewed feedback 与 baseline result 不匹配时直接失败
4. rerun generation 失败时，保留已成功的 feedback apply 结果，但 experiment report 必须明确记录 rerun 失败

这里的关键约束是：  
**主数据路径永远不是 experiment runner 的默认写目标。**

## 9. 测试策略

至少覆盖以下场景：

1. 默认 generation 行为不受 path overrides 影响
2. prepare 会创建完整 workspace、副本文件、baseline result、feedback review、manifest
3. apply 会严格读取 manifest 中的 workspace 路径，而不是主数据路径
4. `keep` 实验能产生可验证的 before/after 漂移
5. `reject` 实验能产生可验证的 before/after 漂移
6. 如果反馈已改分但 rerun 未导致选中变化，report 仍能正确标记 `retrieval_changed_only` 或 `no_observable_change`
7. CLI prepare / apply 路径具备回归测试

## 10. 风险与取舍

1. **feedback 已经生效，但 rerun 结果可能不变**  
   这是允许的。报告必须把“已改分但未改选中结果”与“完全没生效”区分开。

2. **runner 需要 generation 支持路径注入**  
   这会触及主链入口，但通过小型配置对象可以把影响限制在 orchestration 边界。

3. **实验 workspace 会复制多份 evidence 文件**  
   当前文件体量很小，可接受；优先换取隔离性与可重放性。

## 11. 完成标准

完成后，应能稳定验证这条实验路径：

```text
input request
-> create isolated experiment workspace
-> run baseline generation
-> review keep / reject
-> apply feedback into workspace evidence
-> rerun same request against workspace evidence
-> inspect experiment report
```

并且满足：

- 默认主数据未被 runner 隐式修改
- 实验输入与输出都可落盘复查
- 同一实验 workspace 可以被独立审阅或重放
- 用户能直接看到“feedback 是否影响下一轮结果”
