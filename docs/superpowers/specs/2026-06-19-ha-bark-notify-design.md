# Home Assistant Bark Notify 集成 — 设计文档

- **状态**：Draft（待用户 review）
- **日期**：2026-06-19
- **类型**：HACS custom_integration（UI Config Flow）
- **范围**：Bark 客户端推送全部功能（不含服务端）

---

## 1. 目标与非目标

### 目标
- 在 Home Assistant 中通过 HACS 安装本集成，使用 Bark 的全部推送能力。
- 一个 Bark 设备（一台 iPhone/iPad）= 一个 config entry，各自独立实体。
- 仅 UI 配置流程，符合 HA 现代约定。
- 支持自建 bark-server（自定义服务器 URL，默认 `https://api.day.app`）。
- 支持端到端 AES-128-CBC 加密推送。
- 提供独立的强类型 `bark.send` 服务，覆盖 Bark 文档列出的全部参数。
- 配置流程内置测试推送验证；设备页提供 `button.test_push` 随时触发测试推送。
- 完备的错误分层、日志脱敏、单元/集成测试。

### 非目标
- 不实现 Bark 服务端（bark-server）。
- 不创建 `notify.*` 实体（用户已选独立 `bark.send` 服务）。
- 不做自动重试（避免触发 Bark 官方服务器的 BAN 规则）。
- 不实现 diagnostic 失败事件总线（作为可选增强，初版不做）。
- 当前只支持 `aes-128-cbc` 加密算法（代码预留枚举便于扩展）。

---

## 2. 架构概览

标准 HACS custom_integration 骨架：

```
custom_components/bark/
├── manifest.json          # 集成元信息
├── const.py               # 常量、域名、参数 key 映射
├── bark_api.py            # BarkClient：HTTP 推送 + 加密封装（独立可测，不依赖 HA）
├── config_flow.py         # UI 配置流程 + 选项/重配置流程
├── __init__.py            # async_setup_entry：建 client、注册服务、建实体
├── entity.py              # BarkDeviceEntity + button/sensor 实体
├── service.py             # bark.send 服务的 voluptuous schema + handler
├── services.yaml          # bark.send 服务字段描述（HA UI 自动生成）
└── translations/
    ├── en.json
    └── zh-Hans.json

tests/
├── test_bark_api.py
├── test_encryption.py
├── test_service.py
├── test_config_flow.py
└── test_entity.py
```

**职责分离**：
- `bark_api.py` 纯 I/O 与加密，不依赖 HA，可单测。
- `service.py` / `config_flow.py` / `entity.py` 是 HA 适配层。
- 错误由 `bark_api.py` 抛出，HA 层翻译为 `HomeAssistantError` 或 config flow 表单错误。

---

## 3. Config Flow（用户配置流程）

### 首次添加（Settings → Devices & Services → Add Integration → "Bark"）

表单字段：

| 字段 | 类型 | 说明 |
|---|---|---|
| `name` | 文本 | 设备名（如「我的 iPhone」），用于命名实体 |
| `server_url` | 文本 | Bark 服务器，默认 `https://api.day.app`，支持自建 bark-server |
| `device_key` | 文本 | Bark App 复制的 device key |
| `encryption` | 选择 | `none`（默认）/ `aes-128-cbc` |
| `encryption_key` | 文本 | 当 `encryption != none` 时必填，正好 16 字符 |

**IV 处理**：不要求用户配置 IV。每次推送由集成随机生成 16 字节 IV，随请求一并发出（Bark 支持 `iv` 参数）。安全性更高且用户只需保管 key。

**校验步骤**：表单提交后，集成用填入参数发一条测试推送（body: "Bark 已接入 Home Assistant"）。HTTP 200 视为成功并保存 config entry；非 200 显示错误让用户修正。尽早暴露 key 错误、服务器不可达、加密参数不匹配等问题。

**重配置流程（Options/Reconfigure flow）**：允许用户修改 server_url、device_key、加密设置、name，无需删除重加。

**多设备**：用户可重复「Add Integration」为每台设备各建一个 entry，各自独立实体。

---

## 4. BarkClient API 抽象层（`bark_api.py`）

集成核心，负责所有 HTTP 通信与加密。**不依赖 HA**，方便单测。

### 接口
```python
class BarkClient:
    def __init__(self, server_url: str, device_key: str,
                 encryption: str = "none", encryption_key: str | None = None,
                 session: aiohttp.ClientSession | None = None): ...

    async def push(self, payload: BarkPayload) -> BarkResponse: ...
    async def async_close(self) -> None: ...
```

### BarkPayload（dataclass，字段与 Bark 参数一一对应，snake_case 内部使用）
`title, subtitle, body, markdown, level, volume, badge, call, auto_copy, copy, sound, icon, image, group, is_archive, ttl, url, action, id, delete`

### HTTP 协议
统一用 **POST JSON 到 `/{device_key}`**。最可靠（避免 GET URL 编码问题，支持所有字段类型），单一路由简化逻辑。复用一个 `aiohttp.ClientSession`（HA 注入或自建），用 HTTP keep-alive 提高吞吐，符合 Bark FAQ「大量推送请复用连接」要求。

### 响应处理
`BarkResponse(code: int, message: str, timestamp: ...)`，code 200 成功；非 200 抛对应 `BarkPushError` 子类，由调用方决定如何上报。

### 超时
默认 10 秒，可被 config flow 配置覆盖。

---

## 5. `bark.send` 服务 Schema（`service.py` + `services.yaml`）

独立 `bark.send` 服务，用 voluptuous schema 强类型校验，HA UI 自动生成表单与自动补全。

### Target 选择器
服务注册为支持 target（`entity_id` 或 `device_id`），用户可在 UI 里选某个 Bark 设备。多设备时能精准投递，也兼容自动化里用 `entity_id:` 列表。

### 字段 schema（全部字段除 `message` 外可选）

| 字段 | 类型 | 校验 / 说明 |
|---|---|---|
| `message` | string，**必填** | 映射到 Bark `body` |
| `title` | string | Bark `title` |
| `subtitle` | string | Bark `subtitle` |
| `markdown` | string | 传了则忽略 `message`，对应 Bark `markdown` |
| `level` | select | `critical`/`active`/`timeSensitive`/`passive` |
| `volume` | int 0–10 | 仅 `critical` 有效，默认 5 |
| `badge` | int | 角标数字 |
| `sound` | string | 铃声名（如 `minuet`） |
| `icon` | string | 图标 URL |
| `image` | string | 图片 URL |
| `group` | string | 通知分组 |
| `call` | bool | true → Bark `call=1`（重复铃声） |
| `url` | string | 点击跳转 URL |
| `action` | select | 仅 `alert`（不填则不传） |
| `copy` | string | 指定复制内容 |
| `auto_copy` | bool | true → `autoCopy=1` |
| `is_archive` | bool | 是否存档 |
| `ttl` | int | 有效期秒数 |
| `id` | string | 用于更新/删除同 ID 通知 |
| `delete` | bool | true → `delete=1`，搭配 `id` |

### 字段映射规则
- snake_case → Bark camelCase / 不同语义。
- 布尔类字段（`call`/`auto_copy`/`is_archive`/`delete`）统一转成 `"1"` 字符串发送，符合 Bark「传 1 生效」约定。
- `volume` 仅在 `level=critical` 时加入 payload，否则忽略（避免误导）。
- `markdown` 与 `message` 互斥：schema 不强制报错，但 handler 里若 `markdown` 非空则不传 `body`。
- 不加「原始 passthrough」字段，保持强类型清晰。

### handler 执行流
1. 从 `service_call.data` 取 target，解析出对应 config entry → `BarkClient`
2. 构造 `BarkPayload`
3. `await client.push(payload)`
4. 成功：无返回值（HA 服务惯例）；失败：抛 `HomeAssistantError`，HA 自动记录日志并通知用户

### 服务描述文件
`services.yaml` 提供每个字段中文+英文描述，HA 自动生成 UI。`translations/` 下提供 zh-Hans/en 两套。

---

## 6. 实体（`entity.py`）

每个 config entry 创建一个**设备**和若干实体挂在它下面。

### Device（设备对象）
- 名称：用户在 config flow 填的 `name`
- 标识：`device_key` 的哈希（不存原始 key 到设备 registry 元信息里，降低泄露面）
- 型号：`Bark Device`、厂商：`Bark`、SW 版本：集成版本号

### 实体清单（全部挂在同一设备下）

| 实体 | 平台 | 用途 |
|---|---|---|
| `button.test_push` | Button | 点按触发测试推送（body: 「Home Assistant 测试推送」，title: 设备名） |
| `sensor.bark_<name>_last_push_status` | Sensor | 最近一次推送结果：`success` / `failed` / `unknown`（重启后初值） |
| `sensor.bark_<name>_last_push_time` | Sensor (timestamp) | 最近一次推送时间，方便自动化判活 |

### 说明
- **不创建 `notify.*` 实体**：已选独立 `bark.send` 服务。`bark.send` 通过 target 选择器定位设备，实体由诊断实体承担「设备身份」角色。
- **target 解析**：`bark.send` 的 target 可以是上述任一实体的 entity_id，或整个 device_id。handler 用 entity registry 反查所属 config entry，再拿到对应 `BarkClient`。
- **诊断实体更新**：每次 `bark.send`（含 test_push 按钮触发）返回后更新两个 sensor 状态；推送异常时 `last_push_status=failed`，但不阻塞服务调用。
- 不加虚假的「连接状态」实体，避免误导（Bark 推送是单向的）。

---

## 7. 加密处理细节

### 加密触发条件
config entry 里 `encryption != "none"` 时，**所有**推送（含 test_push）都自动加密，用户无需在每次 `bark.send` 调用时指定。

### 参数派生
- **Key**：用户在 config flow 输入的 16 字符 ASCII 字符串，直接取其 UTF-8 bytes 作为 AES-128 key（16 字节 = 128 位）。不做 PBKDF2 等派生，与 Bark App 内置「自定义密钥」期望一致。
- **IV**：每次推送用 `os.urandom(16)` 随机生成，**不复用**。IV 随密文一起通过 `iv` 字段发出（base64），Bark App 用同一 key + 收到的 IV 解密。
- **Padding**：PKCS7（`cryptography` 库 AES-CBC 默认）。
- **输出编码**：ciphertext 与 iv 均 base64 编码后作为 JSON 字段发送。

### Bark 兼容性硬约束（实现时校对依据）
文档示例：key=`1234567890123456`（ASCII），iv=`1234567890123456`，明文 `{"body": "test", "sound": "birdsong"}`，算法 aes-128-cbc，期望密文：
```
+aPt5cwN9GbTLLSFri60l3h1X00u/9j1FENfWiTxhNHVLGU+XoJ15JJG5W/d/yf0
```
测试里固定 IV 跑一遍，应得到完全相同的 ciphertext，验证我们的 key 派生、padding、编码与 openssl/Bark 一致。若不一致（Bark App 实际用了不同 key 派生），以文档示例为基准修正，并在 spec 注明。

### 加密后的请求结构
```
POST /{device_key}
Content-Type: application/json
{
  "ciphertext": "<base64>",
  "iv": "<base64>"
}
```
原 payload 所有字段（title/body/sound…）都**不**明文发送，全部进 ciphertext。device_key 仍走 URL（Bark 服务端需要它路由，且 device_key 本身不是敏感内容——它就是用来寻址的）。

### Key 安全
- config flow 里 `encryption_key` 字段标记为敏感（voluptuous schema 不回显），不写入日志。
- entry 的 data 里以明文存储（HA config entry 没有加密存储机制，这是 HA 平台限制）。

### 加密算法扩展性
当前只实现 `aes-128-cbc`（Bark App 主流用法）。代码用枚举 `EncryptionAlgorithm`，后续若 Bark 新增算法易扩展。

---

## 8. 错误处理与日志

### 错误分层（`bark_api.py` 抛出，HA 层翻译）

| 错误类型 | 触发条件 | 用户可见表现 |
|---|---|---|
| `BarkConnectionError` | 网络/DNS/超时/服务器不可达 | config flow: 「无法连接到 Bark 服务器」；service: `HomeAssistantError("Bark 推送失败：连接超时")` |
| `BarkAuthError` | HTTP 400/401，通常是 device_key 错误 | config flow: 「device_key 无效」；service: `HomeAssistantError`，并记 `ERROR` 日志 |
| `BarkRateLimitError` | HTTP 429（被官方服务器 BAN 24h） | service: `HomeAssistantError("Bark 推送被限流，请稍后重试")`；diagnostic sensor 标 `failed` |
| `BarkServerError` | HTTP 500/502/503 | service: `HomeAssistantError`；建议重试 |
| `BarkPushError`（基类） | 其他非 200 响应 | 附带 `code` 与 `message`（Bark 服务端返回的 message） |
| `BarkEncryptionError` | 加密参数不合法（key 长度错等） | config flow: 「加密 key 必须为 16 字符」 |

### 日志策略
- `INFO`：集成加载、config entry 添加/移除（HA 默认）
- `DEBUG`：每次推送的完整 payload（**加密时不打印明文**，只打印 ciphertext 长度与目标 key 前 4 位）、HTTP 状态码、响应 message
- `WARNING`：可重试类错误（5xx、超时）
- `ERROR`：配置类错误（auth、key 无效）——一次性，避免刷屏
- **敏感信息脱敏**：日志与 diagnostic 里，`device_key` 只显示前 4 + 后 4 位，`encryption_key` 完全不打。封装 `_redact_key()` 辅助函数。

### 重试策略
- **不在集成层做自动重试**：Bark 官方服务器对错误请求有 BAN 机制（5 分钟 1000 次错误请求会被封 24h），自动重试可能加剧封禁。失败的推送由用户/自动化自行重试。
- 配置流程的测试推送**不重试**：一次失败即提示用户修正配置。

---

## 9. 测试策略

### 测试框架
`pytest` + `pytest-aiohttp` + `aiohttp` test server（HA 集成标准做法）。目录：`tests/`，与 `custom_components/bark/` 同级。CI 跑 `pytest`。

### 1. 单元测试 — BarkClient（`tests/test_bark_api.py`），不依赖 HA
- `test_push_success`：mock server 返回 200，断言请求路径、JSON body、字段名正确
- `test_push_400_auth_error`：返回 400 → 抛 `BarkAuthError`，携带 code/message
- `test_push_429_rate_limit`：返回 429 → 抛 `BarkRateLimitError`
- `test_push_500_server_error`：返回 500 → 抛 `BarkServerError`
- `test_push_timeout`：服务器不响应 → 抛 `BarkConnectionError`
- `test_boolean_field_serialization`：`call=True` → payload 里 `"call": "1"`（覆盖全部布尔字段）
- `test_markdown_overrides_body`：`markdown` 非空时 `body` 不进 payload
- `test_volume_only_with_critical`：`level != critical` 时 `volume` 被丢弃

### 2. 加密测试（`tests/test_encryption.py`），关键正确性校验
- `test_encryption_matches_bark_doc_example`：用文档示例 key/IV/明文，**固定 IV** 跑加密，断言密文 = `+aPt5cwN9GbTLLSFri60l3h1X00u/9j1FENfWiTxhNHVLGU+XoJ15JJG5W/d/yf0`
- `test_random_iv_each_push`：两次推送产出不同 ciphertext（IV 随机）
- `test_roundtrip`：用同样 key 解密我们产出的 ciphertext，得到原 payload
- `test_invalid_key_length`：非 16 字符 key → 抛 `BarkEncryptionError`
- `test_no_encryption_when_disabled`：`encryption=none` 时 payload 明文发送，无 ciphertext/iv 字段

### 3. 服务层测试（`tests/test_service.py`）
- `test_service_push_success`：触发 `bark.send`，断言 client.push 被正确参数调用
- `test_service_target_resolution`：多 entry 场景下，按 entity_id 选对 client
- `test_service_required_message`：缺 `message` → voluptuous 校验失败
- `test_service_propagates_error`：client 抛错 → `HomeAssistantError`

### 4. 配置流程测试（`tests/test_config_flow.py`）
- `test_user_flow_success`：填全字段 + mock 测试推送 200 → entry 创建
- `test_user_flow_test_push_fails`：测试推送 400 → 表单报错，entry 不创建
- `test_reconfigure_flow`：改 server_url 后 entry 更新
- `test_encryption_key_required_when_encryption_on`：选 aes-128-cbc 但不填 key → 校验错误

### 5. 实体测试（`tests/test_entity.py`）
- `test_test_push_button`：按下 → client.push 被调用、`last_push_status` → `success`
- `test_sensor_status_on_failure`：推送失败 → sensor → `failed`
- `test_redact_key_in_diagnostics`：diagnostic dump 里 device_key 脱敏

### Mock 策略
HTTP 用 `aiohttp` 内置 test server 或 `aioresponses`；HA runtime 用 `pytest-homeassistant-custom-component`（HA 社区标准测试辅助库，提供 `hass` fixture）。

### 覆盖率目标
`bark_api.py` ≥ 95%（核心逻辑），`service.py` / `config_flow.py` ≥ 85%，整体 ≥ 90%。

---

## 10. 关键决策记录

| 决策点 | 选择 | 理由 |
|---|---|---|
| 多设备模型 | 一个设备一个 config entry | 符合 HA 现代约定，多 entry UI 流程自然 |
| 配置方式 | 仅 UI Config Flow | YAML notify 平台正被 HA 弃用 |
| 服务器端点 | 自定义 URL，默认 api.day.app | 支持自建 bark-server |
| 加密 | 支持 AES-128-CBC | Bark 关键隐私特性 |
| 服务设计 | 独立 `bark.send` 服务 | 强类型校验、UI 自动补全，用户选择 |
| 测试推送 | config flow 验证 + `button.test_push` | 兼顾初次校验与日常使用 |
| notify 实体 | 不创建 | 已有独立服务，避免双入口 |
| 自动重试 | 不做 | 避免 Bark BAN 规则加剧 |

---

## 11. 依赖与运行环境

- **HA 目标版本**：2024.x+（使用现代 config flow、entity.py、services.yaml 约定）
- **Python**：3.12+（随 HA）
- **第三方库**：
  - `aiohttp`（HA 自带，HTTP 客户端）
  - `cryptography`（HA 已打包，AES-128-CBC）
- **测试库**：`pytest`, `pytest-aiohttp`, `pytest-homeassistant-custom-component`
- **manifest.json requirements**：无额外 pip 依赖（全部用 HA 内置库）

---

## 12. 未决事项 / 实现时验证点

1. **加密 key 派生**：当前设计「ASCII bytes 直接作为 AES key」，**必须**用第 7 节的文档示例固定 IV 测试校对。若失败，调研 Bark App 实际派生方式并修正。
2. **HA 测试辅助库兼容性**：`pytest-homeassistant-custom-component` 的版本与目标 HA 版本对齐，实现时确认。
3. **device_key 哈希算法**：device registry 标识用 SHA-256 的前 16 位 hex 即可（不要求密码学强度，只要唯一稳定）。
