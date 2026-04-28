# Refresh Experiment Runner 设计稿

整理日期：2026-04-28

## 1. 目标

当前项目已经具备一条可闭环的 evidence 主链：

```text
public source
-> refresh run
-> promotion review / apply
-> active evidence
```

但这条链目前还缺一层关键验证能力：

```text
这次 refresh / promotion 引入的新 evidence
-> 是否真的改变了 concept 结果
-> 改变发生在哪
-> 是否值得继续保留或扩展
```

这条 change 的目标，是新增一个 **批量 refresh experiment runner**，把一次 `refresh run` 对一组 request 的影响变成可重复、可对比、可复盘的实验流程：

```text
refresh run dir + request set
-> prepare experiment
-> baseline results
-> reviewed promotion
-> apply experiment in isolated evidence copy
-> rerun all requests
-> per-request compare reports
-> aggregate experiment report
```

完成后，系统可以不修改主 evidence，就批量验证一次 refresh/promotion 是否真的带来可观测结果变化。

## 2. 范围

### 2.1 包含

1. 支持以 `refresh run dir` + `request set manifest` 作为实验输入
2. 支持两步式实验流程：
   - `prepare`
   - `apply`
3. 在实验工作区内复制 active evidence 副本
4. 对 request 集合批量运行 baseline result
5. 在实验副本中 apply reviewed promotion
6. 对同一批 request 批量 rerun
7. 生成：
   - baseline results
   - post-apply results
   - per-request compare reports
   - aggregate experiment report
8. 对 compare 报告输出以下核心差异：
   - selected elements
   - retrieved ranking
   - concept score
   - factory_spec 摘要
   - accepted evidence 摘要

### 2.2 不包含

1. render/image generation 实验
2. 图片 diff
3. 自动 accept/reject promotion
4. 多 category
5. 多轮 apply 到同一实验工作区
6. request set 自动发现
7. factory_spec 全量深 diff
8. prompt token 级 diff

## 3. 关键设计决定

### 3.1 这条 change 是“效果验证系统”，不是新业务主链

这次 change 的主要目的不是直接增强最终业务输出，而是回答：

- 这次 refresh evidence 是否真的有效
- 有效变化发生在哪些 request
- 变化属于 selection / retrieval / score / factory_spec 的哪一类

因此这条 change 的本质是 **evidence effect validation harness**，而不是再造一条新的生产主链。

### 3.2 使用批量 request set，而不是单 request

单 request 实验虽然更轻，但无法回答“这次 refresh 整体值不值”。  
批量 request set 才能做：

- 总体 change rate
- 平均 score delta
- 变化类型统计
- 受影响 slot 统计

所以第一版直接支持 request 集合，不先做单 request runner。

### 3.3 使用实验副本，不触碰主 evidence

所有 promotion apply 都只作用于实验工作区内复制出的 evidence 副本：

- `data/mvp/dress/elements.json`
- `data/mvp/dress/strategy_templates.json`
- `data/mvp/dress/evidence_taxonomy.json`

主 evidence 永远不被修改。  
这样实验可以安全复跑、对比、丢弃，也符合前面已确立的 review-gated 工作方式。

### 3.4 采用两步式 prepare/apply，不做一键式

两步式流程：

1. `prepare`
   - 建实验工作区
   - 跑 baseline
   - 生成 `promotion_review.json`
2. `apply`
   - 读取 reviewed promotion
   - apply 到实验副本
   - rerun + compare

这样能保持：

- review gate 不被绕过
- 实验输入稳定
- baseline 与 apply 时刻清晰分离

### 3.5 compare 报告只做“可判断价值”的核心差异

第一版 compare 不追求全量深 diff，而是只输出：

- selected element changes
- retrieval rank changes
- concept score delta
- factory_spec 摘要变化
- accepted evidence 摘要

这样已经足够判断 refresh 是否有效，同时能避免 report 噪音过大。

### 3.6 复用现有 feedback experiment 模式，而不是另起框架

仓库已经存在：

- `temu_y2_women/feedback_experiment_runner.py`

这提供了现成的实验工作区思路：

- workspace manifest
- evidence copy
- baseline / rerun / report

这次 change 复用这种结构，但不把 feedback 与 refresh experiment 强行抽成统一框架。  
统一框架的收益不够大，且会把本次 change 扩大成重构。

## 4. 架构与模块边界

### 4.1 新增 refresh experiment runner

新增：

- `temu_y2_women/refresh_experiment_runner.py`

职责：

- request set manifest 解析
- 实验工作区创建
- evidence 副本复制
- baseline / rerun 批量编排
- promotion review / apply 串接
- per-request compare 构建
- aggregate experiment report 构建

不负责：

- promotion 内容校验规则
- concept generation 核心逻辑
- 图片渲染

### 4.2 新增 refresh experiment runner CLI

新增：

- `temu_y2_women/refresh_experiment_runner_cli.py`

职责：

- 参数解析
- `prepare` / `apply` 子命令调度
- 打印 JSON 结果

CLI 只做薄封装，不承载 compare 或 promotion 规则。

### 4.3 复用现有模块

继续直接复用：

- `temu_y2_women/refresh_run_promotion.py`
- `temu_y2_women/evidence_promotion.py`
- `temu_y2_women/orchestrator.py`
- `temu_y2_women/evidence_paths.py`
- 当前 result 中已有的 `factory_spec` 输出链路

## 5. 输入与工件

### 5.1 request set manifest

第一版 request set 只引用现有 request JSON：

```json
{
  "schema_version": "refresh-experiment-request-set-v1",
  "category": "dress",
  "requests": [
    {
      "request_id": "summer-vacation-a",
      "request_path": "tests/fixtures/requests/dress-generation-mvp/success-summer-vacation-mode-a.json"
    },
    {
      "request_id": "transitional-a",
      "request_path": "tests/fixtures/requests/dress-generation-mvp/success-baseline-transitional-mode-a.json"
    }
  ]
}
```

约束：

- `schema_version` 必须匹配
- `category` 第一版固定 `dress`
- `request_id` 必须唯一
- `request_path` 必须指向可读 JSON 文件

### 5.2 prepare 后工作区结构

```text
<experiment_root>/<experiment_id>/
  experiment_manifest.json
  promotion_review.json
  baseline/
    <request_id>.json
    ...
  data/
    mvp/dress/
      elements.json
      strategy_templates.json
      evidence_taxonomy.json
```

其中：

- `promotion_review.json` 是给人工编辑的 reviewed promotion 起点
- `baseline/` 保存每个 request 的 baseline result
- `data/...` 是实验 evidence 副本

### 5.3 apply 后工作区结构

```text
<experiment_root>/<experiment_id>/
  post_apply/
    <request_id>.json
    ...
  compare/
    <request_id>.json
    ...
  promotion_report.json
  experiment_report.json
```

其中：

- `post_apply/` 保存 rerun 结果
- `compare/` 保存单 request 对比
- `promotion_report.json` 是实验副本上的 promotion 结果
- `experiment_report.json` 是批量聚合报告

## 6. prepare / apply 流程

### 6.1 prepare

输入：

- `--run-dir`
- `--request-set`
- `--experiment-root`
- 可选 `--workspace-name`

流程：

1. 校验 refresh run dir
2. 校验 request set manifest
3. 创建实验工作区
4. 复制 active evidence 到工作区副本
5. 基于 `run_dir` 生成 `promotion_review.json`
6. 对 request 集合逐个运行 baseline result
7. 写 `experiment_manifest.json`

返回：

- `experiment_id`
- `workspace_root`
- `manifest_path`
- `promotion_review_path`
- baseline 结果索引

### 6.2 apply

输入：

- `--manifest`
- 可选 `--reviewed`

若未显式传 `--reviewed`，默认使用工作区中的 `promotion_review.json`。

流程：

1. 读取 manifest
2. 校验 reviewed promotion
3. 在实验副本 evidence 上 apply promotion
4. 对同一批 request 批量 rerun
5. 为每个 request 写：
   - `post_apply/<request_id>.json`
   - `compare/<request_id>.json`
6. 写：
   - `promotion_report.json`
   - `experiment_report.json`

返回关键输出路径与聚合摘要。

## 7. compare report 设计

### 7.1 per-request compare

每个 `compare/<request_id>.json` 至少包含：

- `schema_version`
- `request_id`
- `change_type`
- `baseline_summary`
- `post_apply_summary`
- `diff`
- `accepted_evidence`

重点差异：

- `selected_element_changes`
- `retrieval_rank_changes`
- `concept_score_delta`
- `factory_spec_changes`

### 7.2 `change_type`

稳定分类：

- `selection_changed`
- `retrieval_changed_only`
- `score_changed_only`
- `factory_spec_changed_only`
- `no_observable_change`

### 7.3 factory_spec 差异只做摘要

第一版不做全文深 diff，只记录：

- known section 是否变化
- unresolved count 是否变化
- selected-element-driven known facts 是否变化

这样可以降低噪音，并保持输出稳定可读。

## 8. aggregate experiment report

`experiment_report.json` 负责回答“这次 refresh 值不值”。

至少包含：

- `schema_version`
- `experiment_id`
- `request_count`
- `change_summary`
- `score_summary`
- `slot_change_summary`
- `accepted_evidence_summary`
- `request_reports`

其中：

- `change_summary` 统计各类 `change_type` 的 request 数量
- `score_summary` 记录 changed request 数量、平均 delta、最大/最小 delta
- `slot_change_summary` 统计哪些 slot 最常变化
- `accepted_evidence_summary` 汇总本次 promotion 接受的 element / strategy ids
- `request_reports` 建立 request 与 compare 文件的索引

## 9. 错误处理与 fail-closed

### 9.1 实验输入层错误

新增错误码：

- `INVALID_REFRESH_EXPERIMENT_INPUT`

适用场景：

- request set manifest 非法
- request 文件不存在
- request_id 不唯一
- manifest 缺字段
- workspace 名称冲突

### 9.2 复用已有 refresh / promotion 错误

继续复用：

- `INVALID_REFRESH_RUN`
- `INVALID_PROMOTION_INPUT`
- `INVALID_PROMOTION_REVIEW`
- `PROMOTION_WRITE_FAILED`

### 9.3 实验执行层错误

新增错误码：

- `REFRESH_EXPERIMENT_FAILED`

适用场景：

- baseline 运行失败
- post-apply rerun 失败
- compare report 写入失败
- experiment report 聚合失败

### 9.4 fail-closed 约束

必须保持：

1. prepare 失败时，不留下指向坏状态的 manifest
2. apply 失败时，不输出部分 compare 结果冒充成功
3. 主 evidence 永远不被修改
4. 所有 apply 仅作用于实验副本

## 10. 测试策略

### 10.1 prepare 单测

验证：

- request set manifest 解析正确
- 实验工作区创建正确
- `promotion_review.json` 正确生成
- baseline 结果按 `request_id` 落盘
- `experiment_manifest.json` 路径与索引正确

### 10.2 apply 单测

验证：

- 默认读取工作区里的 `promotion_review.json`
- apply 后只修改实验副本 evidence
- `post_apply/`、`compare/`、`promotion_report.json`、`experiment_report.json` 正确生成
- 缺 reviewed、非法 reviewed、rerun 失败时 fail-closed

### 10.3 批量集成测试

使用 2 个 request + 1 个 refresh run 跑完整链路，断言：

- baseline 与 post-apply 结果都存在
- 至少一个 request 出现可观测变化
- aggregate report 统计正确
- 主 evidence 文件未变

## 11. 完成标准

完成后，系统应满足：

1. 一次 refresh run 可以对一组 request 做批量实验
2. promotion 只在实验副本 evidence 上 apply
3. 系统能批量输出 baseline / post-apply / compare / aggregate report
4. compare 报告能清晰展示：
   - selected elements 变化
   - retrieved ranking 变化
   - concept score 变化
   - factory_spec 摘要变化
   - accepted evidence 摘要
5. 系统可以帮助判断这次 refresh/promotion 是否值得继续保留或扩展

第一版落地后，将形成这条验证闭环：

```text
refresh run dir + request set
-> prepare experiment
-> baseline batch
-> reviewed promotion
-> apply experiment
-> rerun batch
-> compare reports
-> aggregate evidence-impact report
```
