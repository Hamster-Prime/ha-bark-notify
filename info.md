# Bark

通过 [Bark](https://bark.day.app) 向 iPhone/iPad 发送推送通知。

## 功能

- 多设备：每台 iPhone/iPad 一个 config entry
- 自定义服务器（默认 api.day.app，支持自建 bark-server）
- 端到端 AES-128-CBC 加密
- 独立 `bark.send` 服务，覆盖 Bark 全部推送参数
- 配置时自动测试推送；`button.test_push` 随时测试
- 诊断传感器：最近推送状态/时间
