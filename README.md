# HA Bark Notify

通过 [Bark](https://bark.day.app) 向 iPhone/iPad 发送推送通知的 Home Assistant 自定义集成（HACS）。

## 功能

- 一台设备 = 一个 config entry，多设备各自独立
- 自定义服务器 URL（默认 api.day.app，支持自建 bark-server）
- 端到端 AES-128-CBC 加密推送
- 独立的强类型 `bark.send` 服务，覆盖 Bark 全部参数（title/body/markdown/sound/level/badge/icon/image/group/call/url/ttl/id/delete…）
- 配置时自动测试推送验证
- `button.test_push` 随时触发测试推送
- 诊断传感器：最近推送状态、最近推送时间

## 安装

1. 通过 HACS 添加本仓库为自定义仓库（类别：Integration）
2. 在 HACS 安装 "Bark"
3. 重启 Home Assistant
4. Settings → Devices & Services → Add Integration → "Bark"
5. 填入设备名、服务器 URL、设备 Key（在 Bark App 中复制），可选开启加密

## 使用

在自动化中调用 `bark.send`：

```yaml
action: bark.send
data:
  message: "洗衣机洗完了"
  title: "家务提醒"
  group: "home"
  sound: "minuet"
  target_entity: <config entry id 或选择设备实体>
```
