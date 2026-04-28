# Refresh-to-Review Promotion 设计稿

整理日期：2026-04-28

## 1. 目标

当前仓库已经具备两段独立能力：

```text
refresh
-> draft_elements.json / draft_strategy_hints.json / refresh_report.json

promotion
-> prepare review / validate reviewed / apply promotion
```

这条 change 的目标不是重写 promotion 规则，而是把两段能力接成一条可直接操作的人工审阅链路：

```text
refresh run dir
-> prepare promotion review
-> reviewer edits decisions
-> apply reviewed promotion
-> active evidence + promotion_report.json
```

完成后，refresh 产物可以直接进入 review-gated promotion，而不需要人工逐个拼装 staged 文件路径。

## 2. 范围

### 2.1 包含

1. 支持以 `refresh run dir` 作为 promotion 主输入单位
2. 保留现有逐文件 promotion 输入模式
3. 在 `prepare` / `apply` 两个 CLI 子命令中同时支持 `--run-dir`
4. 为 `--run-dir` 建立稳定的默认文件发现与默认输出约定
5. 对 refresh run 目录做结构化校验并返回明确错误
6. 保持现有 promotion 校验、merge 语义与原子写入逻辑不变

### 2.2 不包含

1. 自动 reviewer decision 生成
2. 自动 accept / reject
3. 自动从 refresh 直接 promotion 到 active evidence
4. 修改 promotion review schema
5. 修改 promotion report schema
6. 改写 active evidence 默认路径策略

## 3. 关键设计决定

### 3.1 采用薄编排层，不重写 promotion core

现有 `temu_y2_women/evidence_promotion.py` 已经稳定承担：

- review template 生成
- reviewed decision 校验
- deterministic create/update promotion
- fail-closed 原子写入

因此这条 change 只新增一层“run-dir -> file paths”的编排，不改写现有规则核心。这样风险最低，也能避免两套 promotion 逻辑漂移。

### 3.2 同时支持 `--run-dir` 与逐文件模式

用户已经明确要求两种模式并存：

- `--run-dir`：面向 refresh 链路，使用体验最好
- 逐文件模式：保留当前测试、脚本、手工调试兼容性

CLI 对外主推 `--run-dir`，但不移除现有逐文件参数接口。

### 3.3 `--run-dir` 是完整 refresh run 契约，不是任意目录

`--run-dir` 模式下，目录必须来自一次合法 refresh run。至少要求存在：

- `draft_elements.json`
- `draft_strategy_hints.json`
- `ingestion_report.json`
- `refresh_report.json`

这样可以避免把一个恰好放了两个 draft 文件的普通目录误当成 refresh run，保持来源可追溯。

### 3.4 prepare 与 apply 使用同一 review 文件演进

默认文件策略统一为：

- prepare 默认写：`promotion_review.json`
- apply 默认读优先级：
  1. `--reviewed`
  2. `run_dir/promotion_review.json`
  3. `run_dir/reviewed_decisions.json`

这样新链路可以直接“prepare -> 原地编辑 -> apply”，同时兼容旧 fixture 或已有命名。

### 3.5 active evidence 继续显式传参

这条 change 不为 active evidence 路径引入隐式默认值。CLI 继续要求显式传：

- `--active-elements`
- `--active-strategies`

原因：

- 降低误写主 evidence 风险
- 让测试更容易做临时文件隔离
- 方便未来支持 shadow store 或沙箱 evidence

## 4. 架构与模块边界

### 4.1 保留现有 promotion core

`temu_y2_women/evidence_promotion.py`

职责：

- 加载 staged drafts
- 生成 review template
- 校验 reviewed payload
- apply accepted reviewed records
- 生成 promotion report
- 保持 all-or-nothing 写入

该模块不感知 refresh run 目录结构。

### 4.2 新增 refresh run promotion 编排层

新增：

- `temu_y2_women/refresh_run_promotion.py`

职责：

- 解析 `--run-dir`
- 发现 run 内默认工件路径
- 校验 run 目录契约
- 解析 prepare/apply 默认输出与默认 reviewed 输入
- 调用 `evidence_promotion.py` 现有 API

不负责：

- promotion 内容校验规则
- merge 语义
- active evidence 写入细节

### 4.3 扩展现有 CLI

保留并扩展：

- `temu_y2_women/evidence_promotion_cli.py`

职责：

- 参数解析
- 输入模式判定
- 调用 run-dir 编排层或逐文件模式
- 打印最终 JSON 结果

不新增第二个 promotion CLI，避免入口分裂。

## 5. CLI 设计

### 5.1 子命令保持不变

继续保留：

- `prepare`
- `apply`

不新增 `prepare-from-refresh` 或 `apply-from-refresh`，避免命令面继续膨胀。

### 5.2 prepare 输入规则

prepare 必须二选一：

1. `--run-dir`
2. `--draft-elements` + `--draft-strategy-hints`

且必须提供：

- `--active-elements`
- `--active-strategies`

输出规则：

- 若显式传 `--output`，使用显式值
- 否则在 `--run-dir` 模式下默认写 `run_dir/promotion_review.json`
- 逐文件模式仍要求显式 `--output`

### 5.3 apply 输入规则

apply 必须二选一：

1. `--run-dir`
2. `--draft-elements` + `--draft-strategy-hints`

且必须提供：

- `--active-elements`
- `--active-strategies`

reviewed 读取规则：

1. 若显式传 `--reviewed`，使用该路径
2. 否则在 `--run-dir` 模式下先找 `run_dir/promotion_review.json`
3. 若不存在，再兼容回退 `run_dir/reviewed_decisions.json`

report 输出规则：

- 若显式传 `--report-output`，使用显式值
- 否则在 `--run-dir` 模式下默认写 `run_dir/promotion_report.json`
- 逐文件模式仍要求显式 `--report-output`

### 5.4 输入模式不混用

当传入 `--run-dir` 时，不允许再传：

- `--draft-elements`
- `--draft-strategy-hints`

允许覆盖项只保留：

- `--output`
- `--reviewed`
- `--report-output`

这样可以避免 staged 输入来源歧义。

## 6. run-dir 契约与文件约定

给定：

```text
data/refresh/dress/<run_id>/
```

run-dir 模式下默认使用：

```text
draft_elements.json
draft_strategy_hints.json
ingestion_report.json
refresh_report.json
promotion_review.json
promotion_report.json
```

其中：

- 前四个是 refresh 必需输入工件
- `promotion_review.json` 是 prepare 默认产物与 apply 默认优先读取对象
- `promotion_report.json` 是 apply 默认产物

review 过程发生在同一 run 目录内，保证 refresh、review、promotion 报告天然聚合。

## 7. 错误处理

### 7.1 参数与 run-dir 层错误

新增结构化错误码：

- `INVALID_REFRESH_RUN`

适用场景：

- `--run-dir` 缺少必需工件
- `--run-dir` 与逐文件 staged 输入混用
- apply 在 run-dir 模式下找不到 reviewed 文件
- prepare/apply 所需默认路径无法解析

这层错误只说明“编排输入不成立”，不说明 promotion 内容本身有问题。

### 7.2 promotion 内容层错误继续复用

继续复用现有错误码：

- `INVALID_PROMOTION_INPUT`
- `INVALID_PROMOTION_REVIEW`
- `PROMOTION_WRITE_FAILED`
- `PROMOTION_IO_FAILED`

这样能明确区分：

- 目录契约错误
- staged / reviewed 内容错误
- 输出写入错误

## 8. 行为约束与 fail-closed

必须保持：

1. `prepare` 只生成 review 文件，不改 active evidence
2. `apply` 只有在 reviewed 全量校验通过后才写 active evidence
3. apply 失败时不写部分 elements、不写部分 strategies、不写部分 report
4. run-dir 编排层不能绕过现有 promotion 校验

也就是说，refresh-to-review-promotion 只是“更顺手的入口”，不是更宽松的入口。

## 9. 测试策略

### 9.1 编排层单测

验证：

- run-dir 默认 staged 文件解析正确
- reviewed 默认查找顺序正确
- 缺必需 run 工件时返回 `INVALID_REFRESH_RUN`
- 混用 `--run-dir` 与 staged 文件参数时失败

### 9.2 CLI 单测

验证：

- `prepare --run-dir` 能打印结果并默认写 `promotion_review.json`
- `apply --run-dir` 能读取默认 reviewed 并默认写 `promotion_report.json`
- `--output` / `--reviewed` / `--report-output` 覆盖有效
- 逐文件模式仍保持当前行为

### 9.3 端到端集成测试

用临时目录种入 refresh 工件与 promotion fixture，验证：

```text
refresh run dir
-> prepare
-> edit reviewed decisions
-> apply
-> active evidence updated
-> promotion_report.json written
```

同时验证：

- prepare 不修改 active evidence
- apply 失败时 active evidence 保持不变
- report 落在预期 run 目录

## 10. 完成标准

完成后，项目应满足：

1. refresh run 目录可直接作为 promotion 输入
2. CLI 同时支持 `--run-dir` 与逐文件模式
3. reviewer 可在 run 目录内直接编辑同一份 review 文件
4. apply 结果能回写到同一 run 目录
5. promotion core 的 merge、validation、all-or-nothing 语义保持不变

最终可落地的最小闭环为：

```text
public refresh run dir
-> promotion_review.json
-> reviewer edits decisions
-> promotion apply
-> active evidence
-> promotion_report.json
```
