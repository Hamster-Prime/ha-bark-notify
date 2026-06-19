<div align="center">

# 🐶 HA Bark Notify

**通过 [Bark](https://bark.day.app) 给 iPhone / iPad 发推送通知的 Home Assistant 自定义集成**

轻量 · 端到端加密 · 覆盖 Bark 全部推送参数 · 一台设备一份配置

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/hacs/integration)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](#许可证)
[![Home Assistant](https://img.shields.io/badge/Home%20Assistant-2024.4%2B-41BDF5.svg)](https://www.home-assistant.io/)
[![Bark](https://img.shields.io/badge/Bark-Official%20App-000000.svg)](https://bark.day.app)

</div>

---

## ✨ 功能特性

- 📱 **多设备独立配置** — 每台 iPhone / iPad 一个 config entry，互不干扰
- 🔒 **端到端 AES-128-CBC 加密** — 与 Bark iOS App 互通（密文连 Bark 服务器和苹果 APNs 都看不到，已用官方文档示例密文逐字节验证）
- 🌐 **自定义服务器** — 默认 `https://api.day.app`，也支持自建 [bark-server](https://github.com/Finb/bark-server) 部署
- 🛠 **强类型 `bark.send` 服务** — 覆盖 Bark 全部 20 个推送参数（标题 / 正文 / Markdown / 铃声 / 中断级别 / 角标 / 图标 / 图片 / 分组 / 重复响铃 / 跳转 URL / 有效期 / 通知 ID …）
- 🧪 **配置时自动测试推送** — 填完表单即发一条验证推送，错误立即暴露，不让坏配置进 HA
- 🔔 **`button.test_push` 一键测试** — 设备页直接点按按钮即可触发测试推送，日常排障最方便
- 📊 **诊断传感器** — `last_push_status`（success / failed / unknown）+ `last_push_time`，自动化判活有依据
- 🛡 **隐私安全** — 设备 Key 在 HA 设备注册表里以 SHA-256 哈希存储；日志里 Key 自动脱敏（仅显示前 4 + 后 4 位）；每次加密推送生成随机 IV

---

## 📦 安装

### 通过 HACS（推荐）

1. 打开 Home Assistant 的 **HACS** → **Integrations**
2. 右上角 ⋮ → **Custom repositories**
3. **Repository** 填：`https://github.com/Hamster-Prime/ha-bark-notify`
4. **Category** 选 `Integration` → **Add**
5. 在 HACS 搜索 **Bark** → **Download**
6. **完全重启 Home Assistant**（不是 reload，必须重启）
7. **Settings → Devices & Services → Add Integration** → 搜索 "Bark"
8. 填入：
   - **设备名称**：任意（如 "我的 iPhone"）
   - **服务器地址**：`https://api.day.app` 或你的自建 bark-server 地址
   - **设备 Key**：在 Bark App 首页复制的 URL 最后一段（`https://api.day.app/XXXXXX` 中的 `XXXXXX`）
   - **加密**：可选 `AES-128-CBC`，需填 16 字符密钥（须与 Bark App 内置加密设置一致）
9. 提交后会自动发一条测试推送；手机收到即配置成功

> 💡 **多设备**：重复第 7-9 步，为每台 iPhone / iPad 各建一个 entry。

---

## 🚀 使用

### 在自动化 / 脚本里调用 `bark.send`

最简调用：

```yaml
action: bark.send
data:
  message: "洗衣机洗完了"
  target_entity: <你的 Bark 设备实体或 config entry id>
```

完整字段示例（覆盖 Bark 全部能力）：

```yaml
action: bark.send
data:
  message: "洗衣机洗完了"          # 必填，推送正文
  title: "家务提醒"                # 推送标题
  subtitle: "次要说明"             # 副标题
  # markdown: "# 标题\n正文"       # 传了 markdown 会忽略 message
  level: timeSensitive             # critical / active / timeSensitive / passive
  volume: 7                        # 仅 level=critical 生效，0-10
  badge: 1                         # App 角标数字
  sound: minuet                    # 铃声名（在 Bark App 内预览）
  icon: https://example.com/i.png  # 自定义图标 URL（自动缓存）
  image: https://example.com/p.jpg # 推送图片
  group: home                      # 通知分组
  call: false                      # true = 重复响铃（接电话式提醒）
  url: https://example.com         # 点击推送跳转的 URL
  action: alert                    # 点击推送时弹出操作弹窗
  copy: "复制内容"                 # 下拉推送时复制到剪贴板
  auto_copy: false                 # 是否自动复制
  is_archive: true                 # 是否保存到 Bark 历史记录
  ttl: 86400                       # 历史记录有效期（秒），到期自动删除
  id: "washer-001"                 # 用相同 id 再次推送会更新通知，不新增
  # delete: true                   # 配合 id 使用，删除指定通知
  target_entity: <Bark 设备实体>
```

### 触发测试推送（两种方式）

**方式 1**：在设备页找到 `button.test_push` 按钮，点击即可。

**方式 2**：在自动化里调用：

```yaml
action: button.press
target:
  entity_id: button.bark_<设备名>_test_push
```

### 监听推送结果（用于告警链路）

```yaml
# 当推送失败时切换某个 boolean 开关
trigger:
  - platform: state
    entity_id: sensor.bark_<设备名>_last_push_status
    to: "failed"
action:
  - service: notify.admin
    data:
      message: "Bark 推送失败，请检查"
```

---

## 🏗 架构总览

```
┌─────────────────────────────────────────────────────────────────┐
│                        Home Assistant                            │
│                                                                  │
│   ┌──────────────────┐   ┌──────────────────┐   ┌────────────┐  │
│   │  Config Flow     │   │   bark.send      │   │  Entities  │  │
│   │  (用户/重配置)   │──▶│    Service       │──▶│            │  │
│   │                  │   │                  │   │ • button   │  │
│   │ • 表单 + 验证    │   │ • voluptuous     │   │ • sensor×2 │  │
│   │ • 测试推送       │   │   schema (20字段)│   │            │  │
│   └────────┬─────────┘   │ • 目标解析       │   └─────▲──────┘  │
│            │             │   (entry/entity/ │         │         │
│            │             │    device)       │         │ 事件    │
│            │             └────────┬─────────┘         │ 订阅    │
│            │                      │                   │         │
│            ▼                      ▼                   │         │
│   ┌──────────────────────────────────────────────────┐│         │
│   │              BarkClient (HA-independent)         │└─────────┘
│   │                                                  │
│   │   hass.data[DOMAIN][entry_id]                    │
│   │   ├─ client: BarkClient                          │
│   │   └─ runtime: {status, time}  ◀── 传感器读这里   │
│   └──────────────────────┬───────────────────────────┘
│                          │ aiohttp POST JSON
└──────────────────────────┼─────────────────────────────────────┘
                           ▼
                   ┌────────────────┐
                   │  bark-server   │  ← api.day.app 或自建
                   │  (官方/自建)   │
                   └────────┬───────┘
                            │ APNs (Apple Push Notification service)
                            ▼
                   ┌────────────────┐
                   │  Bark iOS App  │  ← 端到端解密
                   └────────────────┘
```

### 文件结构与职责

```
custom_components/bark/
├── manifest.json          # HA 集成元信息（域名、版本、依赖）
├── hacs.json              # HACS 商店元信息
├── const.py               # 全部常量（DOMAIN、CONF_*、运行时 key）
├── bark_api.py            # 【核心】BarkClient + BarkPayload + 错误类
│                          #        + encrypt_payload（纯 Python，不依赖 HA）
├── config_flow.py         # UI 配置流程（用户步骤 + 重配置）
├── __init__.py            # async_setup_entry/unload_entry + 运行时状态
├── entity.py              # BarkEntity 基类 + 设备绑定 + redact_key
├── button.py              # button.test_push 实体
├── sensor.py              # last_push_status + last_push_time 诊断传感器
├── service.py             # bark.send 服务的 schema + handler
├── services.yaml          # bark.send 字段描述（HA UI 自动生成表单）
└── translations/
    ├── en.json            # 英文翻译
    └── zh-Hans.json       # 简体中文翻译
```

### 关键设计决策

| 决策点 | 选择 | 理由 |
|---|---|---|
| 多设备模型 | 一台设备一个 config entry | 符合 HA 现代约定，多 entry 自然隔离 |
| 配置方式 | 仅 UI Config Flow | HA 正在弃用 YAML notify 平台 |
| 服务设计 | 独立 `bark.send` 服务 | 强类型 voluptuous schema，UI 自动补全，比 `notify.*` 的 data 字典更清晰 |
| 加密 | AES-128-CBC，IV 随机 | Bark 关键隐私特性；密文与官方示例字节级一致 |
| 服务器端点 | 自定义 URL，默认 api.day.app | 同时支持官方和自建 bark-server |
| 错误处理 | 分层异常 + 不自动重试 | 避免触发 Bark 官方 5 分钟 1000 次错误请求封 IP 24h 的规则 |
| notify 实体 | 不创建 | 已有独立 `bark.send` 服务，避免双入口混淆 |
| Session 管理 | 复用 HA 共享 aiohttp session | HA 统一管理连接生命周期，避免泄漏 |

---

## 🔒 加密原理（端到端）

本集成支持 Bark 的端到端加密推送：**只有你的 iPhone 能解密内容**，Bark 服务器和苹果 APNs 都看不到明文。

工作流程：

1. 在 Bark iOS App 内开启「推送加密」，选择 `AES-128-CBC` 算法，填入一个 16 字符密钥
2. 在本集成的配置表单里填入**同一个** 16 字符密钥
3. 每次推送时，集成会：
   - 把 payload JSON 用 AES-128-CBC 加密（PKCS7 padding）
   - 随机生成 16 字符 IV（每次不同，前向安全）
   - 仅发送 `{ciphertext, iv}`，**所有明文字段（标题/正文/铃声…）都不出本机**
4. iPhone 收到后用同一密钥 + 收到的 IV 解密

**密钥派生方式**：直接用密钥的 ASCII 字节作为 AES-128 密钥（16 字符 = 16 字节 = 128 位，无 PBKDF2 / 无 HKDF）。这与 Bark iOS App 的实现一致 —— 我们已经用 Bark App 自己生成的加密脚本（`openssl enc -aes-128-cbc`）的输出字节级验证过互通性。

> ⚠️ 16 字符必须是 ASCII 字符。中文字符 / emoji 会被 UTF-8 编码成多字节，导致密钥字节数 ≠ 16。

---

## 🩺 故障排查

| 现象 | 可能原因 | 解决 |
|---|---|---|
| 配置时提示「测试推送失败」 | device_key 错误 / 服务器地址错误 / 网络不通 | 在 Bark App 重新复制 URL 末段；用 `curl` 验证服务器可达 |
| 手机收到「Decryption Failed」 | 加密密钥与 App 内不一致 / 非 16 ASCII 字符 | 重新核对密钥；确保密钥是 16 个 ASCII 字符 |
| 推送延迟很久 | 服务器限流 / APNs 拥堵 / 设备休眠 | 见 [Bark FAQ](https://bark.day.app/#/faq) |
| `last_push_status` 长期 `failed` | 同上原因，看 HA 日志里的 `bark` 报错 | Settings → Logs → 搜 `bark` |
| 多设备只有一台收到 | device_key 在多设备间复用了 | 每个 device_key 只能绑一台设备，给每台设备各配一个 |

**查看详细日志**：在 `configuration.yaml` 开启 debug：

```yaml
logger:
  logs:
    custom_components.bark: debug
```

---

## ❓ FAQ

**Q：为什么不用 HA 标准的 `notify.*` 服务？**
A：Bark 有 20 个参数，`notify` 平台的 `data` 字典无类型校验、UI 不补全。独立 `bark.send` 服务用 voluptuous schema，HA 自动生成表单、自动补全字段、参数错误立即报错，体验显著更好。

**Q：自建 bark-server 怎么配？**
A：在配置表单的「服务器地址」填你的 bark-server 地址（如 `http://192.168.1.100:8080`），其余步骤相同。

**Q：可以同时给多台 iPhone 发同一条消息吗？**
A：可以。在 `bark.send` 的 `target` 里选多个设备实体（或 `entity_id` 列表），handler 会逐个推送。

**Q：HACS 没显示图标 / 没出现更新？**
A：HACS 有缓存。版本号 bump 时才会重新拉取仓库元数据。在 HACS 三角菜单里点 **Check for updates**，必要时 **Redownload** 一次。

**Q：升级到新版后怎么生效？**
A：HACS 更新后**必须完全重启 Home Assistant**（不仅是 reload integration），因为加密代码在 `bark_api.py` 里，重启才会重新加载。

---

## 🤝 致谢

- [Bark](https://bark.day.app) — 由 [@Finb](https://github.com/Finb) 开发的优秀 iOS 推送 App，免费、开源、无广告
- [bark-server](https://github.com/Finb/bark-server) — Bark 官方服务端
- [Home Assistant](https://www.home-assistant.io/) — 开源智能家居平台
- [HACS](https://hacs.xyz/) — Home Assistant Community Store

---

## 📝 许可证

MIT License — 详见 [LICENSE](LICENSE)。

> Bark 是 [Finb](https://github.com/Finb) 的独立项目，本集成与 Bark 作者无隶属关系，仅作为客户端实现推送功能。
