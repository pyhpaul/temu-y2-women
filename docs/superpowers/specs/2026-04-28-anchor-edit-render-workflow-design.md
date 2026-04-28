# Anchor + Edit Render Workflow 设计稿

整理日期：2026-04-28

## 1. 目标

当前仓库的 6 图链路虽然已经能稳定产出：

- `hero_front`
- `hero_three_quarter`
- `hero_back`
- `construction_closeup`
- `fabric_print_closeup`
- `hem_and_drape_closeup`

但执行方式仍是 **6 次彼此独立的图片生成**。这会导致：

- 同一款衣服在不同图之间出现花型、裙摆、腰线、模特姿态漂移
- 多图看起来更像“同风格变体”，而不是“同一件衣服的不同视角 / 细节”

本次 change 的目标，是把当前主链升级为：

1. 先生成 1 张 `hero_front` 作为 **anchor**
2. 再基于 anchor 通过 `images/edits` 派生剩余 5 张图
3. 任一派生失败时 **fail-fast**
4. 不自动回退到独立 generate

这条 change 的成功标准不是“生成成功率最高”，而是 **明确验证并落地一条以一致性优先的主链**。

## 2. 范围

### 2.1 包含

1. 把 `render_jobs` 从“独立 prompt 列表”升级为“显式渲染执行计划”
2. 为每个 job 增加 `render_strategy` 与 `reference_prompt_id`
3. 让 `prompt_renderer` 产出：
   - 1 个 `generate` anchor job
   - 5 个 `edit` derived jobs
4. 让 workflow 顺序执行：
   - 先 `generate hero_front`
   - 再 `edit` 其余 5 图
5. 为 OpenAI-compatible provider 增加 `images.edit` 调用能力
6. 在 render report 中记录每张图的执行策略与参考来源

### 2.2 不包含

- 自动回退到独立 generate
- 多 anchor / 多参考图融合
- mask 编辑
- 多图一致性评分器
- 更细的生产元数据自动补全
- 非 OpenAI-compatible provider 的 edit 适配

## 3. 关键设计决定

### 3.1 render job 改为显式执行计划，而不是“6 条独立 prompt”

当前 `render_jobs` 中每个 job 只有：

- `prompt_id`
- `group`
- `output_name`
- `prompt`

这不足以表达：

- 某张图应该走 `generate`
- 还是应该走 `edit`
- `edit` 时引用哪张已生成图片

本次将 job 结构升级为：

- `prompt_id`
- `group`
- `output_name`
- `prompt`
- `render_strategy`
- `reference_prompt_id`（仅 `edit` 使用）

其中：

- `prompt` 在 `generate` job 中表示完整生成 prompt
- `prompt` 在 `edit` job 中表示编辑指令

### 3.2 `hero_front` 是唯一 anchor

本轮不引入多 anchor，也不引入“先主图、再细节图重新找更近裁切”的二次参考链。

统一规则：

- `hero_front`：`render_strategy = "generate"`
- 其余 5 张图：`render_strategy = "edit"`
- 所有 `edit` job 的 `reference_prompt_id = "hero_front"`

这样：

- 视角图和细节图都绑定到同一个服装主体
- 路径最短，验证最直接
- 失败原因也最容易定位

### 3.3 fail-fast，不自动 fallback

本轮明确不做：

- “如果 edit 失败，就偷偷改成 generate”

原因：

1. 这会把一致性失败伪装成链路成功
2. 产物会混入风格打架的图，污染实验判断
3. 用户当前优先目标是验证同款一致性，不是提高成功率

因此执行策略为：

- `hero_front` 生成成功后，任一 derived edit 失败
- 整个 6 图任务直接返回结构化错误
- 不发布部分成功结果

### 3.4 保留双 key 语义，但把路由理由从“prompt_id 特判”升级为“执行策略”

前一条 change 已经接入：

- `OPENAI_COMPAT_ANCHOR_API_KEY`
- `OPENAI_COMPAT_EXPANSION_API_KEY`

本轮保留这一配置，但语义要更清楚：

- anchor `generate` job 使用 anchor key
- derived `edit` job 使用 expansion key

也就是说，路由依据不再只是“是不是 `hero_front`”，而是：

- `render_strategy == "generate"` → anchor key
- `render_strategy == "edit"` → expansion key

### 3.5 prompt bundle 版本号升级

由于 `render_jobs` 语义已经从“多条生成 prompt”升级为“混合 generate/edit 的执行计划”，本轮将：

- `template_version: visual-prompt-v1`

升级为：

- `template_version: visual-prompt-v2`

旧结果文件若没有新字段，仍按 legacy 单图 / 独立 job 兼容读取，不强制迁移历史产物。

## 4. 模块结构

### 4.1 `temu_y2_women/prompt_renderer.py`

职责调整：

- 继续生成 anchor 完整 prompt
- 为 derived jobs 生成 edit instruction，而不是独立生成 prompt
- 产出带 `render_strategy` / `reference_prompt_id` 的 `render_jobs`
- `detail_prompts` 保留，但同步带上新字段，便于调试与人工审阅

### 4.2 `temu_y2_women/image_generation_output.py`

职责调整：

- 解析新的 `render_jobs` 字段
- 在 `ImageRenderJob` / `ImageRenderInput` 中承载：
  - `render_strategy`
  - `reference_prompt_id`
  - `reference_image_bytes`（运行时注入，不落盘）
- 保持 legacy 单图输入兼容：
  - 无 `render_jobs` 时默认构造 1 个 `generate` job

### 4.3 `temu_y2_women/image_generation_workflow.py`

职责调整：

- 从“无状态逐 job 调 provider”
- 改成“顺序执行并缓存已生成图片”

执行顺序：

1. 执行 `hero_front generate`
2. 缓存其图片字节
3. 后续 `edit` job 根据 `reference_prompt_id` 取参考图片
4. 参考图片缺失或 edit 失败时 fail-fast

### 4.4 `temu_y2_women/image_generation_openai.py`

职责调整：

- 继续支持 `images.generate`
- 新增 `images.edit`
- 根据 `render_strategy` 选择调用路径
- `edit` 请求带：
  - `image`
  - `prompt`
  - `model`
  - `size`
  - `quality`
  - `response_format="b64_json"`
  - `input_fidelity="high"`

## 5. 数据契约

### 5.1 新版 `render_jobs`

每个 job 至少包含：

```json
{
  "prompt_id": "hero_back",
  "group": "hero",
  "output_name": "hero_back.png",
  "prompt": "Keep the exact same garment identity and only rotate to a back view...",
  "render_strategy": "edit",
  "reference_prompt_id": "hero_front"
}
```

### 5.2 legacy 兼容规则

如果输入结果仍是旧结构：

- 没有 `render_jobs`
- 或 `render_jobs` 没有 `render_strategy`

则按以下兼容逻辑：

- 单图 legacy 结果：构造成 1 个 `generate` job
- 历史多 job 结果：缺省 `render_strategy = "generate"`

这保证旧 fixture 和旧产物仍能被读取。

## 6. prompt 策略

### 6.1 anchor prompt

`hero_front` 继续使用完整服装主图 prompt，保持现在的：

- 商品主体
- 结构
- 工艺/面料表现
- 场景与光线
- 约束与避免项

### 6.2 edit instruction

derived jobs 不再把自己写成“独立生成 prompt”，而是写成：

- 明确保持同一件衣服
- 明确保持花型位置 / 版型 / 面料 / 模特造型
- 只改变视角或展示部位

例如：

- `hero_three_quarter`：只改成三分之四视角
- `hero_back`：只改成背视角
- `construction_closeup`：只放大领口、胸部结构、缝线

## 7. 输出与可观测性

render report 中每张图新增：

- `render_strategy`
- `reference_prompt_id`

保留：

- `prompt_id`
- `group`
- `output_name`
- `prompt_fingerprint`
- `image_path`

顶层：

- `image_path` 仍指向第一张图（即 `hero_front`）

## 8. 错误处理

新增或细化以下错误场景：

1. `reference image missing`
   - `edit` job 声明了 `reference_prompt_id`
   - 但 workflow 缓存里找不到对应图片

2. `unsupported render strategy`
   - 既不是 `generate` 也不是 `edit`

3. `edit returned no image payload`
   - `images.edit` 成功返回但没有图片

4. `edit provider failed`
   - OpenAI SDK 或上游兼容网关抛错

错误 details 中应尽量带上：

- `prompt_id`
- `render_strategy`
- `reference_prompt_id`

## 9. 测试策略

### 9.1 `tests/test_prompt_renderer.py`

覆盖：

- `hero_front` 为 `generate`
- 其余 5 张图为 `edit`
- `reference_prompt_id == "hero_front"`
- `template_version == "visual-prompt-v2"`

### 9.2 `tests/test_image_generation_output.py`

覆盖：

- 新字段解析
- legacy 单图兼容
- 历史多 job 缺省 `render_strategy="generate"` 兼容

### 9.3 `tests/test_image_generation_openai.py`

覆盖：

- `generate` 调 `images.generate`
- `edit` 调 `images.edit`
- `edit` 带参考图文件和 `input_fidelity="high"`

### 9.4 `tests/test_image_generation_workflow.py`

覆盖：

- 顺序执行 generate → edit
- reference 缺失时报错
- 任一 edit 失败时 fail-fast
- report 带 `render_strategy` / `reference_prompt_id`

### 9.5 真实烟测

至少验证：

- `hero_front generate`
- `hero_back edit`

确认新 key 的 `gpt-image-2 images/edits` 真链路可跑。

## 10. 完成标准

完成后，仓库应满足：

1. 6 图主链默认走 `1 generate + 5 edits`
2. `hero_front` 是唯一 anchor
3. 其余 5 张图都显式绑定 `hero_front`
4. 任一 derived edit 失败时整次任务 fail-fast
5. report 可明确看出每张图是 `generate` 还是 `edit`
6. 旧单图结果文件仍可被兼容读取
7. 使用 `gpt-image-2` 时，最小 anchor+edit 真实烟测通过
