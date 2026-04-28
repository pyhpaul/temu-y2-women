# OpenAI-Compatible Image Provider Config 设计稿

整理日期：2026-04-28

## 1. 目标

当前仓库已经具备：

- `generate_and_render_cli` 一体化生成与渲染入口
- `image_generation_cli` 基于已落盘结果的渲染入口
- `openai` / `fake` 两类图片 provider
- `3` 张主图 + `3` 张细节图的图片生成链路

但当前 `openai` provider 只能读取 `OPENAI_API_KEY` 环境变量，不能：

- 读取 `~/.codex/config.toml` 里的 `base_url`
- 读取 `~/.codex/auth.json` 里的 `OPENAI_API_KEY`
- 通过 CLI 显式覆盖 endpoint 与认证

本次 change 的目标，是把现有 `openai` provider 扩成一条 **OpenAI-compatible endpoint 可配置链路**，优先支持用户当前机器上的 Aerorelay 配置，同时不改变现有 6 图产物、prompt 结构和工作流入口语义。

## 2. 范围

### 2.1 包含

1. 为 `openai` provider 增加共享配置解析层
2. 从 `~/.codex/config.toml` 读取 `base_url`
3. 从 `~/.codex/auth.json` 读取 `OPENAI_API_KEY`
4. 两条 CLI 同步支持 `--base-url` 与 `--api-key`
5. 保持 CLI 显式参数优先级最高
6. 在渲染结果中补充最终使用的 `provider / model / base_url`

### 2.2 不包含

- 新增 `aerorelay` provider 名称
- 自动读取更多图片参数（如从本机配置推断 `model` / `size` / `style`）
- 修改 prompt 结构
- 修改 6 图位定义
- 多图一致性增强
- 更细的工厂生产元数据补全

## 3. 关键设计决定

### 3.1 保留 `--provider openai`，不引入新 provider 名

Aerorelay 当前被视为 OpenAI-compatible endpoint。调用链只需要支持：

- 自定义 `base_url`
- 自定义认证来源

因此本次继续保留 `--provider openai`，避免把同一协议能力拆成两套 provider 语义。

### 3.2 新增共享配置解析模块，provider 层只做调用

现有 `image_generation_openai.py` 同时承担：

- 配置读取
- provider 构造
- SDK 请求

这会导致两条 CLI 如果都要支持本机配置回退，就只能复制读取逻辑。本次新增一个共享配置解析模块，职责限定为：

- 合并 CLI 参数
- 回退读取环境变量
- 回退读取 `~/.codex/config.toml` / `~/.codex/auth.json`
- 生成一个已解析的 provider 配置对象

`image_generation_openai.py` 只负责：

- 接收解析后的配置
- 初始化 SDK client
- 发起图片生成请求

### 3.3 配置优先级显式化

配置优先级统一定义为：

#### `api_key`

1. CLI `--api-key`
2. 环境变量 `OPENAI_API_KEY`
3. `~/.codex/auth.json` 中的 `OPENAI_API_KEY`

#### `base_url`

1. CLI `--base-url`
2. `~/.codex/config.toml` 中的 `base_url`
   - 优先读取顶层 `base_url`
   - 若未配置，则读取当前 `model_provider` 对应的 `model_providers.<name>.base_url`
3. SDK 默认地址

#### 其他参数

- `model`
- `size`
- `quality`
- `background`
- `style`

继续使用 CLI 值；若未显式传入，则保持现有默认值。

### 3.4 fake provider 不读取任何 OpenAI 兼容配置

`--provider fake` 继续保持完全本地行为：

- 不读取 `config.toml`
- 不读取 `auth.json`
- 不依赖环境变量

避免测试与本机配置发生耦合。

### 3.5 输出可观测但不泄露密钥

成功渲染后的输出结果需要记录：

- `provider`
- `model`
- `base_url`

但明确禁止输出：

- `api_key`
- `Authorization`
- `auth.json` 原始内容

## 4. 模块结构

### 4.1 新增模块

新增：

- `temu_y2_women/image_provider_config.py`

建议责任划分：

- 解析 CLI provider 相关参数
- 解析本机 `.codex` 配置文件
- 合并优先级
- 生成 `ResolvedOpenAIImageConfig` 之类的结构化配置对象

### 4.2 修改模块

#### `temu_y2_women/image_generation_openai.py`

- 接受 `base_url`
- 接受已解析好的 `api_key`
- 不再直接读取环境变量

#### `temu_y2_women/generate_and_render_cli.py`

- 新增 `--base-url`
- 新增 `--api-key`
- 调用共享配置解析模块

#### `temu_y2_women/image_generation_cli.py`

- 新增 `--base-url`
- 新增 `--api-key`
- 调用共享配置解析模块

## 5. 配置文件契约

### 5.1 `~/.codex/config.toml`

本轮消费：

- 顶层 `base_url`
- 或当前 `model_provider` 指向的 `model_providers.<name>.base_url`

如果文件不存在，则忽略。
如果文件存在但无法解析，则返回结构化配置错误。

### 5.2 `~/.codex/auth.json`

本轮只消费：

- 顶层 `OPENAI_API_KEY`

如果文件不存在，则忽略。
如果文件存在但无法解析，则返回结构化配置错误。

### 5.3 路径处理

代码实现不应写死 Windows 绝对路径，而应默认通过：

- `Path.home() / ".codex" / "config.toml"`
- `Path.home() / ".codex" / "auth.json"`

同时允许测试注入自定义路径，避免单测依赖真实用户目录。

## 6. CLI 合同变化

两条 CLI 都新增：

- `--base-url`
- `--api-key`

保留现有：

- `--provider`
- `--model`
- `--size`
- `--quality`
- `--background`
- `--style`

行为要求：

1. `--provider fake` 不读取 OpenAI 配置
2. `--provider openai` 先用 CLI 显式值
3. 缺失显式值时按约定优先级回退
4. 结果 JSON 中应出现 `base_url`
5. 结果 JSON 中不应出现 `api_key`

## 7. 错误处理

### 7.1 配置解析错误

继续使用 `INVALID_IMAGE_PROVIDER_CONFIG`，但补充更具体的 `details`：

- `field`
- `path`（如配置文件路径）
- `sources_tried`
- `provider`

典型场景：

- `api_key` 缺失
- `config.toml` 非法
- `auth.json` 非法

### 7.2 provider 调用错误

远端请求失败、无图片返回、SDK 抛错等，继续走现有：

- `IMAGE_PROVIDER_FAILED`

本轮不改变调用层错误码语义。

## 8. 测试策略

### 8.1 配置解析单测

覆盖：

- CLI `--api-key` 覆盖环境变量和 `auth.json`
- 环境变量覆盖 `auth.json`
- `auth.json` 提供 `OPENAI_API_KEY`
- `config.toml` 提供 `base_url`
- `config.toml` 缺失时回退到 SDK 默认地址
- `auth.json` 缺失且无其他来源时报结构化错误
- `fake` provider 不触发配置读取

### 8.2 CLI 测试

两条入口都要覆盖：

- 自动读取本机配置成功路径
- `--base-url` 显式覆盖路径
- `--api-key` 显式覆盖路径
- 缺 key 的失败路径
- 输出包含 `base_url`
- 输出不包含 `api_key`

### 8.3 provider 测试

覆盖：

- provider 构造时可接收 `base_url`
- client 初始化时把 `base_url` 传给 SDK
- 缺失 `api_key` 仍 fail-closed

## 9. 完成标准

完成后，仓库应满足：

1. `generate_and_render_cli` 可在 `--provider openai` 下自动读取 `~/.codex/config.toml` 和 `~/.codex/auth.json`
2. `image_generation_cli` 具备同样行为
3. CLI 显式参数优先于本机配置
4. fake provider 行为保持不变
5. 成功输出中可见 `provider / model / base_url`
6. 任意输出中都不泄露 `api_key`
7. 现有 6 图生成链路、prompt 结构、产物命名保持不变
