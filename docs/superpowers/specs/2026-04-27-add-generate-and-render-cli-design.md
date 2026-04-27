# One-shot Generate and Render CLI 设计稿

整理日期：2026-04-27

## 1. 目标

这次 change 不替换现有两步命令，而是在当前已经具备的：

```text
request json
-> concept generation
-> saved result json
-> image render
```

之上补一条更短的离线执行链路：

```text
request json
-> concept generation
-> persisted concept_result.json
-> image render
-> rendered artifacts
```

完成后，仓库应同时具备两种稳定使用方式：

1. 继续使用现有两步链路，便于分段调试
2. 使用 one-shot CLI 一次性完成生成与渲染，便于快速实验

## 2. 范围

### 包含

1. 新增独立 one-shot CLI 入口
2. 新增独立 orchestration workflow，串联 concept generation 与 image render
3. 在成功生成 concept 后持久化 `concept_result.json`
4. 复用现有 image render workflow 与 provider 参数面
5. 为新 CLI 补齐 success / failure / module entrypoint 测试

### 不包含

- 改写现有 `temu_y2_women.cli` 的默认行为
- 改写现有 `temu_y2_women.image_generation_cli` 的职责
- 新增 gallery、review UI 或批量任务调度
- 新增图片 provider 类型
- 为 one-shot 流程引入新的报告 schema

## 3. 设计选型

### 3.1 方案对比

#### 方案 A：新增独立 CLI + 独立 workflow + 保留中间 result（采用）

- 优点：
  - 不破坏现有两个 CLI 的边界和测试
  - workflow 可独立测试，CLI 不会演化成大函数
  - `concept_result.json` 可保留，便于复现、排查、二次渲染
  - 最符合当前仓库已有的“工作流与 CLI 分层”模式
- 代价：
  - 新增一个 CLI 入口
  - 输出目录会多一个中间 artifact

#### 方案 B：新增 CLI，但 orchestration 全部写在 CLI 内

- 优点：改动最短
- 缺点：
  - CLI 易膨胀
  - 不利于满足函数长度与职责边界约束
  - 复用与测试粒度较差

#### 方案 C：新增 CLI，但 concept result 只写临时文件

- 优点：复用现有 render workflow，最终目录更干净
- 缺点：
  - `source_result_path` 会退化为临时路径
  - 失败排查与二次渲染不方便
  - provenance 不如持久化 result 清晰

### 3.2 采用结论

采用 **方案 A：新增独立 CLI + 独立 workflow + 保留中间 result**。

这次 change 的目标是补足更短的实验链路，而不是把现有两个命令重新揉成一个高耦合入口。

## 4. 工作流

### 4.1 输入

one-shot CLI 接收：

- `--input`
- `--output-dir`
- `--provider {fake,openai}`
- `--model`
- `--size`
- `--quality`
- `--background`
- `--style`

其中 provider 相关可选参数沿用现有 image generation CLI 语义，不引入新的配置概念。

### 4.2 成功路径

执行顺序：

1. 读取并解析 request JSON
2. 调用 `generate_dress_concept(...)`
3. 若 generation 成功，则将完整结果写入 `output_dir/concept_result.json`
4. 调用现有 `render_dress_concept_image(...)`，并将 `concept_result.json` 作为 render source
5. 输出目录写出：
   - `concept_result.json`
   - `rendered_image.png`
   - `image_render_report.json`
6. stdout 打印 render report JSON

### 4.3 失败路径

按阶段 fail-closed：

1. request 读取或 JSON 解析失败：
   - 返回结构化错误
   - 不写任何 artifact
2. concept generation 返回 error：
   - 直接透传错误
   - 不调用 render
   - 不写任何 artifact
3. `concept_result.json` 写盘失败：
   - 返回 `CONCEPT_RESULT_OUTPUT_FAILED`
   - 不调用 render
4. render provider 配置失败、provider dispatch 失败、render 输出发布失败：
   - 保留已成功写出的 `concept_result.json`
   - 不留下部分最终 render bundle

这里的关键语义是：
**render 阶段继续保持 fail-closed，但已成功生成的 concept result 作为可复用中间成果应被保留。**

## 5. 关键模块边界

### 5.1 `generate_and_render_workflow.py`

新增独立 workflow 模块，负责：

- 读取 request JSON
- 调用 concept generation
- 持久化 `concept_result.json`
- 组装 provider
- 调用现有 render workflow
- 返回最终 JSON 结果

该模块不重新实现 generation 或 render 逻辑，只做 orchestration。

为了满足复杂度约束，workflow 内部应拆分为多个小 helper，例如：

- request loading
- concept result persistence
- provider resolution
- render invocation

### 5.2 `generate_and_render_cli.py`

新增独立 CLI 模块，负责：

- 参数解析
- 调用 workflow
- 打印 JSON
- 返回 exit code

CLI 不承载业务判断，不直接实现文件写入、provider 选择细节或 render rollback 逻辑。

### 5.3 现有模块保持稳定

以下模块 contract 保持不变：

- `temu_y2_women.cli`
- `temu_y2_women.image_generation_cli`
- `temu_y2_women.image_generation_workflow`

新的 one-shot 能力建立在它们之上，不回改已有用法。

## 6. 输出契约

### 6.1 输出目录

成功时输出目录固定包含：

- `concept_result.json`
- `rendered_image.png`
- `image_render_report.json`

### 6.2 stdout 契约

stdout 直接打印 `image_render_report.json` 同结构 JSON。

不新增 `one_shot_report.json` 或额外 schema，原因是：

1. 现有 render report 已足够表达 provider、model、image path、report path 与 source result path
2. 下游消费端无需学习新的报告格式
3. `source_result_path` 可以自然指向持久化后的 `concept_result.json`

## 7. 错误处理

### 7.1 新增错误语义

one-shot 流程需要明确两类新错误：

- `INVALID_GENERATE_AND_RENDER_INPUT`
  - request 文件不存在、不可读取、JSON 非法、根对象不是 object
- `CONCEPT_RESULT_OUTPUT_FAILED`
  - `concept_result.json` 无法写入目标目录

其余错误尽量复用现有 error contract，例如：

- `INVALID_REQUEST`
- `INVALID_IMAGE_PROVIDER_CONFIG`
- `IMAGE_PROVIDER_FAILED`
- `IMAGE_RENDER_OUTPUT_FAILED`

### 7.2 原子性边界

这次 change 不追求“整个 one-shot 成功前目录完全为空”的全链路原子性。  
采用的边界是：

- generation 成功前：不写 artifact
- `concept_result.json` 成功后：它本身视为已完成中间成果
- render 成功前：不发布部分最终 render bundle

这个边界更利于复现与重跑，也更符合当前 render workflow 的文件导向设计。

## 8. 测试策略

至少覆盖以下场景：

1. workflow success
   - 写出 `concept_result.json`
   - 写出 `rendered_image.png`
   - 写出 `image_render_report.json`
   - 返回值与 render report 一致
2. request 输入非法
   - 返回 `INVALID_GENERATE_AND_RENDER_INPUT`
   - 不写任何 artifact
3. generation 返回 error
   - 不调用 render
   - 不写任何 artifact
4. concept result 写盘失败
   - 返回 `CONCEPT_RESULT_OUTPUT_FAILED`
   - 不调用 render
5. render 失败
   - 保留 `concept_result.json`
   - 不留下最终 image/report
6. CLI fake provider success
7. CLI openai 缺少 API key failure
8. module entrypoint 在 repo root 外仍可运行

## 9. 风险与取舍

1. **one-shot CLI 会增加入口数量**  
   这是有意取舍。入口增加换来现有 contract 稳定与职责清晰。

2. **render 失败时目录并非完全为空**  
   这是有意保留的中间成果，而不是残缺输出。保留下来的只有可重用的 `concept_result.json`。

3. **stdout 只打印 render report，不回显完整 concept result**  
   这是为了保持和现有 render CLI 一致，同时避免在 one-shot 成功路径上重复输出过多信息。
