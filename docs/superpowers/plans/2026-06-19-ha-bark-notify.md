# Bark Notify 集成 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 实现一个 HACS 可安装的 Home Assistant custom_integration，覆盖 Bark 客户端全部推送功能（含 AES-128-CBC 加密、多设备、测试推送、强类型 `bark.send` 服务）。

**Architecture:** 一个 Bark 设备 = 一个 config entry。`BarkClient`（`bark_api.py`）封装 HTTP + 加密，不依赖 HA，可独立单测。HA 适配层（`config_flow.py` / `__init__.py` / `service.py` / `entity.py`）负责配置流程、服务注册、实体生命周期。加密推送用 AES-128-CBC，每次随机 IV。

**Tech Stack:** Python 3.12 / Home Assistant 2024.x+ / aiohttp（HA 内置）/ cryptography（HA 内置，AES-128-CBC）/ voluptuous / pytest + pytest-asyncio + pytest-aiohttp + pytest-homeassistant-custom-component。

**Spec:** `docs/superpowers/specs/2026-06-19-ha-bark-notify-design.md`

---

## 文件结构

```
ha-bark-notify/
├── custom_components/bark/
│   ├── __init__.py            # async_setup_entry / unload，建 client，注册服务，建实体
│   ├── manifest.json          # 集成元信息
│   ├── const.py               # 常量
│   ├── bark_api.py            # BarkClient + BarkPayload + BarkResponse + 错误类 + encrypt_payload
│   ├── config_flow.py         # UI 配置流程 + Reconfigure 流程
│   ├── entity.py              # 设备 + button.test_push + 诊断 sensors
│   ├── service.py             # bark.send 服务的 schema + handler + target 解析
│   ├── services.yaml          # bark.send 字段描述
│   └── translations/
│       ├── en.json
│       └── zh-Hans.json
├── tests/
│   ├── __init__.py
│   ├── conftest.py            # 公共 fixtures（aiohttp test server、hass、enable_custom_integrations）
│   ├── test_bark_api.py       # BarkClient 单元测试
│   ├── test_encryption.py     # 加密原语测试（含 Bark 文档示例硬约束）
│   ├── test_payload.py        # BarkPayload 序列化测试
│   ├── test_config_flow.py
│   ├── test_service.py
│   └── test_entity.py
├── hacs.json                  # HACS 元信息
├── info.md                    # HACS 商店展示
├── README.md
└── pyproject.toml             # 测试依赖
```

**关键类型（贯穿全计划，保持一致）：**
- `BarkPayload`（dataclass，20 个字段，snake_case 内部命名，`to_bark_dict()` 产出 Bark wire 格式）
- `BarkResponse(code: int, message: str, timestamp: int | None)`
- 错误类层级：`BarkError`（基类）→ `BarkConnectionError` / `BarkAuthError` / `BarkRateLimitError` / `BarkServerError` / `BarkEncryptionError`；`BarkPushError(code, message)` 用于其他非 200 响应
- `BarkClient(server_url, device_key, encryption, encryption_key, session, timeout)`
- `encrypt_payload(payload_json: str, key: str) -> tuple[str, str]` 返回 `(ciphertext_b64, iv_b64)`
- 运行时状态：`hass.data[DOMAIN][entry.entry_id]` 存 `BarkClient`；`hass.data.setdefault(DOMAIN, {})["_runtime"][entry_id]` 存 `{status, time}`，通过事件 `f"{DOMAIN}_push_update"` 通知 sensors

---

## Task 1: 项目骨架与测试依赖

**Files:**
- Create: `custom_components/bark/manifest.json`
- Create: `custom_components/bark/const.py`
- Create: `custom_components/bark/__init__.py`（空骨架）
- Create: `hacs.json`
- Create: `info.md`
- Create: `README.md`
- Create: `.gitignore`
- Create: `pyproject.toml`
- Create: `tests/__init__.py`
- Create: `tests/conftest.py`
- Create: `pytest.ini`

- [ ] **Step 1: 创建 `custom_components/bark/manifest.json`**

> 注：`codeowners` / `documentation` / `issue_tracker` 里的 GitHub 用户名是占位，用户需替换为自己仓库的实际信息。这些值不影响集成运行。

```json
{
  "domain": "bark",
  "name": "Bark",
  "documentation": "https://github.com/your-github-username/ha-bark-notify",
  "issue_tracker": "https://github.com/your-github-username/ha-bark-notify/issues",
  "codeowners": ["@your-github-username"],
  "config_flow": true,
  "iot_class": "cloud_push",
  "requirements": [],
  "version": "1.0.0"
}
```

- [ ] **Step 2: 创建 `custom_components/bark/const.py`**

```python
"""Constants for the Bark integration."""

DOMAIN = "bark"

CONF_NAME = "name"
CONF_DEVICE_KEY = "device_key"
CONF_SERVER_URL = "server_url"
CONF_ENCRYPTION = "encryption"
CONF_ENCRYPTION_KEY = "encryption_key"

DEFAULT_SERVER_URL = "https://api.day.app"
DEFAULT_TIMEOUT = 10

ENCRYPTION_NONE = "none"
ENCRYPTION_AES_128_CBC = "aes-128-cbc"

SERVICE_SEND = "send"

EVENT_PUSH_UPDATE = f"{DOMAIN}_push_update"
ATTR_ENTRY_ID = "entry_id"
ATTR_STATUS = "status"
ATTR_TIME = "time"

STATUS_SUCCESS = "success"
STATUS_FAILED = "failed"
STATUS_UNKNOWN = "unknown"
```

- [ ] **Step 3: 创建 `custom_components/bark/__init__.py`（最小骨架）**

```python
"""The Bark integration."""

from .const import DOMAIN

__all__ = ["DOMAIN"]
```

- [ ] **Step 4: 创建 `hacs.json`**

```json
{
  "name": "Bark",
  "render_readme": true,
  "homeassistant": "2024.4.0",
  "country": ["CN"]
}
```

- [ ] **Step 5: 创建 `info.md`**

```markdown
# Bark

通过 [Bark](https://bark.day.app) 向 iPhone/iPad 发送推送通知。

支持：自定义服务器、端到端 AES-128-CBC 加密、多设备、测试推送、独立的 `bark.send` 服务（覆盖 Bark 全部参数）。
```

- [ ] **Step 6: 创建 `README.md`**

```markdown
# HA Bark Notify

Home Assistant custom_integration for [Bark](https://bark.day.app) push notifications.

**状态：开发中**

设计文档：`docs/superpowers/specs/2026-06-19-ha-bark-notify-design.md`
```

- [ ] **Step 7: 创建 `.gitignore`**

```gitignore
__pycache__/
*.py[cod]
*.egg-info/
.pytest_cache/
.venv/
.coverage
htmlcov/
.DS_Store
```

- [ ] **Step 8: 创建 `pyproject.toml`（测试依赖）**

```toml
[project]
name = "ha-bark-notify"
version = "1.0.0"
requires-python = ">=3.12"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
```

- [ ] **Step 9: 创建 `pytest.ini`**

```ini
[pytest]
asyncio_mode = auto
testpaths = tests
```

- [ ] **Step 10: 创建 `tests/__init__.py`（空文件）**

内容为空字符串。

- [ ] **Step 11: 创建 `tests/conftest.py`（最小骨架，后续任务扩展）**

```python
"""Shared test fixtures."""

import pytest

pytest_plugins = ("pytest_homeassistant_custom_component",)
```

- [ ] **Step 12: 安装测试依赖并验证 pytest 可加载**

Run:
```bash
pip install pytest pytest-asyncio pytest-aiohttp pytest-homeassistant-custom-component cryptography
pytest --collect-only
```
Expected: 至少能收集（可能 0 个测试，但不报 import 错误）。

- [ ] **Step 13: Commit**

```bash
git add custom_components/ tests/ hacs.json info.md README.md .gitignore pyproject.toml pytest.ini
git commit -m "chore: scaffold bark integration project"
```

---

## Task 2: BarkPayload 数据类与序列化

**Files:**
- Create: `tests/test_payload.py`
- Create: `custom_components/bark/bark_api.py`（仅 `BarkPayload` 部分；错误类与 client 后续任务补）

> 说明：本任务先在 `bark_api.py` 中加入 `BarkPayload`（以及后续任务复用的 import 头）。错误类与 `BarkClient` 在后续任务逐步追加到同一文件。

- [ ] **Step 1: 写失败测试 `tests/test_payload.py`**

```python
"""Tests for BarkPayload serialization."""

from custom_components.bark.bark_api import BarkPayload


def test_body_serialized():
    payload = BarkPayload(body="hello")
    assert payload.to_bark_dict() == {"body": "hello"}


def test_markdown_overrides_body():
    payload = BarkPayload(body="hello", markdown="# title")
    data = payload.to_bark_dict()
    assert data == {"markdown": "# title"}
    assert "body" not in data


def test_full_field_mapping_and_camelcase():
    payload = BarkPayload(
        title="t",
        subtitle="st",
        body="b",
        level="critical",
        volume=7,
        badge=3,
        call=True,
        auto_copy=True,
        copy="copied",
        sound="minuet",
        icon="https://example.com/i.png",
        image="https://example.com/img.png",
        group="g",
        is_archive=True,
        ttl=60,
        url="https://example.com",
        action="alert",
        id="abc",
        delete=True,
    )
    assert payload.to_bark_dict() == {
        "body": "b",
        "title": "t",
        "subtitle": "st",
        "level": "critical",
        "volume": 7,
        "badge": 3,
        "call": "1",
        "autoCopy": "1",
        "copy": "copied",
        "sound": "minuet",
        "icon": "https://example.com/i.png",
        "image": "https://example.com/img.png",
        "group": "g",
        "isArchive": "1",
        "ttl": 60,
        "url": "https://example.com",
        "action": "alert",
        "id": "abc",
        "delete": "1",
    }


def test_volume_only_with_critical_level():
    payload = BarkPayload(level="active", volume=7)
    data = payload.to_bark_dict()
    assert data == {"level": "active"}
    assert "volume" not in data


def test_bool_false_omitted():
    payload = BarkPayload(body="x", call=False, delete=False, is_archive=False, auto_copy=False)
    assert payload.to_bark_dict() == {"body": "x"}


def test_none_fields_omitted():
    payload = BarkPayload()
    assert payload.to_bark_dict() == {}
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_payload.py -v`
Expected: FAIL，`ImportError: cannot import name 'BarkPayload'`。

- [ ] **Step 3: 在 `custom_components/bark/bark_api.py` 实现 `BarkPayload`**

```python
"""Bark API client and data types."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class BarkPayload:
    """Bark push payload (internal snake_case names)."""

    title: str | None = None
    subtitle: str | None = None
    body: str | None = None
    markdown: str | None = None
    level: str | None = None
    volume: int | None = None
    badge: int | None = None
    call: bool | None = None
    auto_copy: bool | None = None
    copy: str | None = None
    sound: str | None = None
    icon: str | None = None
    image: str | None = None
    group: str | None = None
    is_archive: bool | None = None
    ttl: int | None = None
    url: str | None = None
    action: str | None = None
    id: str | None = None
    delete: bool | None = None

    def to_bark_dict(self) -> dict[str, Any]:
        """Convert to Bark wire-format dict (camelCase, bools as '1')."""
        data: dict[str, Any] = {}
        if self.markdown:
            data["markdown"] = self.markdown
        elif self.body is not None:
            data["body"] = self.body
        if self.title is not None:
            data["title"] = self.title
        if self.subtitle is not None:
            data["subtitle"] = self.subtitle
        if self.level is not None:
            data["level"] = self.level
            if self.level == "critical" and self.volume is not None:
                data["volume"] = self.volume
        if self.badge is not None:
            data["badge"] = self.badge
        if self.call:
            data["call"] = "1"
        if self.auto_copy:
            data["autoCopy"] = "1"
        if self.copy is not None:
            data["copy"] = self.copy
        if self.sound is not None:
            data["sound"] = self.sound
        if self.icon is not None:
            data["icon"] = self.icon
        if self.image is not None:
            data["image"] = self.image
        if self.group is not None:
            data["group"] = self.group
        if self.is_archive:
            data["isArchive"] = "1"
        if self.ttl is not None:
            data["ttl"] = self.ttl
        if self.url is not None:
            data["url"] = self.url
        if self.action is not None:
            data["action"] = self.action
        if self.id is not None:
            data["id"] = self.id
        if self.delete:
            data["delete"] = "1"
        return data
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_payload.py -v`
Expected: PASS（全部 6 个测试）。

- [ ] **Step 5: Commit**

```bash
git add tests/test_payload.py custom_components/bark/bark_api.py
git commit -m "feat(api): add BarkPayload dataclass with wire serialization"
```

---

## Task 3: 加密原语 `encrypt_payload`（AES-128-CBC）

**Files:**
- Create: `tests/test_encryption.py`
- Modify: `custom_components/bark/bark_api.py`（追加错误类 + `encrypt_payload`）

**关键正确性约束**：Bark 文档示例 — key=`1234567890123456`（ASCII）、IV=`1234567890123456`（ASCII）、明文 `{"body": "test", "sound": "birdsong"}`，期望密文 `+aPt5cwN9GbTLLSFri60l3h1X00u/9j1FENfWiTxhNHVLGU+XoJ15JJG5W/d/yf0`。本任务必须复现此密文。

- [ ] **Step 1: 写失败测试 `tests/test_encryption.py`**

```python
"""Tests for Bark AES-128-CBC encryption."""

import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from custom_components.bark.bark_api import (
    BarkEncryptionError,
    encrypt_payload,
)

DOC_KEY = "1234567890123456"
DOC_IV = "1234567890123456"
DOC_PLAINTEXT = '{"body": "test", "sound": "birdsong"}'
DOC_EXPECTED_CIPHERTEXT = "+aPt5cwN9GbTLLSFri60l3h1X00u/9j1FENfWiTxhNHVLGU+XoJ15JJG5W/d/yf0"


def test_encryption_matches_bark_doc_example():
    """Hard constraint: our crypto must interoperate with Bark/openssl."""
    ciphertext, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY, iv=DOC_IV.encode("utf-8"))
    assert ciphertext == DOC_EXPECTED_CIPHERTEXT
    assert iv == base64.b64encode(DOC_IV.encode("utf-8")).decode()


def test_random_iv_each_push():
    ct1, iv1 = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    ct2, iv2 = encrypt_payload(DOC_PLAINTEXT, DOC_KEY)
    assert iv1 != iv2
    assert ct1 != ct2


def test_roundtrip_decrypt():
    ciphertext, iv = encrypt_payload(DOC_PLAINTEXT, DOC_KEY, iv=DOC_IV.encode("utf-8"))
    key_bytes = DOC_KEY.encode("utf-8")
    iv_bytes = base64.b64decode(iv)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv_bytes))
    decryptor = cipher.decryptor()
    padded = decryptor.update(base64.b64decode(ciphertext)) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    assert plaintext.decode("utf-8") == DOC_PLAINTEXT


def test_invalid_key_length_raises():
    try:
        encrypt_payload(DOC_PLAINTEXT, "too-short")
    except BarkEncryptionError:
        return
    raise AssertionError("expected BarkEncryptionError for short key")
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_encryption.py -v`
Expected: FAIL，`ImportError: cannot import name 'encrypt_payload'`。

- [ ] **Step 3: 在 `bark_api.py` 顶部追加错误类与 `encrypt_payload`**

在文件 `from __future__ import annotations` 之后、`BarkPayload` 之前插入：

```python
import base64
import os
from enum import Enum

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7


class BarkError(Exception):
    """Base class for Bark errors."""


class BarkConnectionError(BarkError):
    """Network / DNS / timeout / unreachable server."""


class BarkAuthError(BarkError):
    """HTTP 400/401 — typically a bad device key."""


class BarkRateLimitError(BarkError):
    """HTTP 429 — rate limited / banned by server."""


class BarkServerError(BarkError):
    """HTTP 5xx — server-side error."""


class BarkPushError(BarkError):
    """Other non-200 responses. Carries the server code and message."""

    def __init__(self, code: int, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(f"Bark push failed ({code}): {message}")


class BarkEncryptionError(BarkError):
    """Invalid encryption parameters."""


class EncryptionAlgorithm(str, Enum):
    NONE = "none"
    AES_128_CBC = "aes-128-cbc"


def encrypt_payload(
    payload_json: str,
    key: str,
    iv: bytes | None = None,
) -> tuple[str, str]:
    """Encrypt payload_json with AES-128-CBC.

    Args:
        payload_json: plaintext JSON string to encrypt.
        key: 16-character ASCII key (AES-128).
        iv: optional fixed IV (for testing interop). Random if omitted.

    Returns:
        Tuple of (ciphertext_b64, iv_b64).
    """
    if len(key) != 16:
        raise BarkEncryptionError("encryption key must be exactly 16 characters")
    key_bytes = key.encode("utf-8")
    if iv is None:
        iv = os.urandom(16)
    cipher = Cipher(algorithms.AES(key_bytes), modes.CBC(iv))
    encryptor = cipher.encryptor()
    padder = PKCS7(algorithms.AES.block_size).padder()
    padded = padder.update(payload_json.encode("utf-8")) + padder.finalize()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return (
        base64.b64encode(ciphertext).decode(),
        base64.b64encode(iv).decode(),
    )
```

- [ ] **Step 4: 运行测试验证通过**

Run: `pytest tests/test_encryption.py -v`
Expected: PASS（全部 4 个测试）。

> **如果 `test_encryption_matches_bark_doc_example` 失败**：说明 key 派生方式与 Bark App 不一致。记录失败的实际密文，调研后修正 `encrypt_payload`（例如尝试 hex 解码 key），重跑直到通过。这是与 Bark App 互通的硬约束，不允许跳过。

- [ ] **Step 5: Commit**

```bash
git add tests/test_encryption.py custom_components/bark/bark_api.py
git commit -m "feat(api): add AES-128-CBC encryption matching Bark doc example"
```

---

## Task 4: BarkClient — 成功推送路径

**Files:**
- Create: `tests/test_bark_api.py`
- Modify: `tests/conftest.py`（加 aiohttp test server fixture）
- Modify: `custom_components/bark/bark_api.py`（追加 `BarkResponse` + `BarkClient`）

- [ ] **Step 1: 扩展 `tests/conftest.py` 加入 aiohttp test server fixture**

替换 `tests/conftest.py` 全文为：

```python
"""Shared test fixtures."""

from typing import Any

import pytest
from aiohttp import web

pytest_plugins = ("pytest_homeassistant_custom_component",)


@pytest.fixture
def bark_server_received():
    """Captures the last request received by the test server."""
    return {"requests": []}


@pytest.fixture
async def bark_server(aiohttp_server, bark_server_received):
    """A mock bark-server that returns configurable responses.

    Defaults to a 200 success. Set ``bark_server_received["status"]`` and
    ``["body"]`` to change behavior, and ``["delay"]`` to simulate slowness.
    Inspect captured requests via ``bark_server_received["requests"]``.
    """

    async def handler(request: web.Request) -> web.Response:
        bark_server_received["method"] = request.method
        bark_server_received["path"] = request.path
        bark_server_received["headers"] = dict(request.headers)
        try:
            bark_server_received["json"] = await request.json()
        except Exception:
            bark_server_received["json"] = None
        bark_server_received["requests"].append(request.path)
        status: int = bark_server_received.get("status", 200)
        body: Any = bark_server_received.get(
            "body", {"code": 200, "message": "success", "timestamp": 1700000000}
        )
        return web.json_response(body, status=status)

    app = web.Application()
    app.router.add_post("/{tail:.*}", handler)
    return await aiohttp_server(app)
```

- [ ] **Step 2: 写失败测试 `tests/test_bark_api.py`（成功路径）**

```python
"""Tests for BarkClient."""

import aiohttp
import pytest

from custom_components.bark.bark_api import (
    BarkClient,
    BarkPayload,
    BarkResponse,
)


@pytest.fixture
async def client_to(bark_server):
    """Return a factory creating a BarkClient pointed at the test server."""
    def _make(**kwargs):
        defaults = {
            "server_url": str(bark_server.make_url("")),
            "device_key": "TESTKEY",
        }
        defaults.update(kwargs)
        return BarkClient(**defaults)
    return _make


async def test_push_success_returns_response(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        resp = await client.push(BarkPayload(body="hello"))
    assert isinstance(resp, BarkResponse)
    assert resp.code == 200
    assert resp.message == "success"
    assert resp.timestamp == 1700000000


async def test_push_posts_json_to_device_key_path(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        await client.push(BarkPayload(body="hello", title="t"))
    assert bark_server_received["method"] == "POST"
    assert bark_server_received["path"] == "/TESTKEY"
    assert bark_server_received["headers"]["Content-Type"] == "application/json"
    assert bark_server_received["json"] == {"body": "hello", "title": "t"}
```

- [ ] **Step 3: 运行测试验证失败**

Run: `pytest tests/test_bark_api.py -v`
Expected: FAIL，`ImportError: cannot import name 'BarkClient'`。

- [ ] **Step 4: 在 `bark_api.py` 末尾追加 `BarkResponse` 与 `BarkClient`（仅成功路径）**

在文件末尾追加：

```python
import json

import aiohttp


@dataclass
class BarkResponse:
    """Bark server response."""

    code: int
    message: str
    timestamp: int | None = None


class BarkClient:
    """Async Bark push client."""

    def __init__(
        self,
        server_url: str,
        device_key: str,
        encryption: str = "none",
        encryption_key: str | None = None,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 10,
    ) -> None:
        self._server_url = server_url.rstrip("/")
        self._device_key = device_key
        self._encryption = encryption
        self._encryption_key = encryption_key
        self._timeout = timeout
        self._session = session
        self._owns_session = session is None

    def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None:
            self._session = aiohttp.ClientSession()
            self._owns_session = True
        return self._session

    async def async_close(self) -> None:
        if self._session is not None and self._owns_session:
            await self._session.close()
            self._session = None

    async def push(self, payload: BarkPayload) -> BarkResponse:
        body = payload.to_bark_dict()
        if self._encryption == EncryptionAlgorithm.AES_128_CBC.value:
            payload_json = json.dumps(body, ensure_ascii=False, separators=(",", ":"))
            ciphertext, iv = encrypt_payload(payload_json, self._encryption_key or "")
            body = {"ciphertext": ciphertext, "iv": iv}
        url = f"{self._server_url}/{self._device_key}"
        session = self._get_session()
        try:
            async with session.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise BarkConnectionError(f"failed to reach bark server: {err}") from err
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            data = {}
        code = int(data.get("code", resp.status))
        message = data.get("message", "")
        timestamp = data.get("timestamp")
        if resp.status == 200 and code == 200:
            return BarkResponse(code=code, message=message, timestamp=timestamp)
        raise BarkPushError(code, message or text)
```

> 注：`import json` 和 `import aiohttp` 放在文件末尾是为了分任务追加的清晰性。最终文件里可以把它们移到顶部 import 区（Task 14 清理会做）。但为了让本任务测试通过，放末尾同样有效。

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_bark_api.py -v`
Expected: PASS（2 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_bark_api.py tests/conftest.py custom_components/bark/bark_api.py
git commit -m "feat(api): add BarkClient success push path with JSON POST"
```

---

## Task 5: BarkClient — 错误映射（400/401/429/500/超时）

**Files:**
- Modify: `tests/test_bark_api.py`（追加错误测试）
- Modify: `custom_components/bark/bark_api.py`（`push` 内补充状态码映射）

- [ ] **Step 1: 追加失败测试到 `tests/test_bark_api.py`**

```python
from custom_components.bark.bark_api import (
    BarkAuthError,
    BarkConnectionError,
    BarkPushError,
    BarkRateLimitError,
    BarkServerError,
)


async def test_push_400_raises_auth_error(client_to, bark_server_received):
    bark_server_received["status"] = 400
    bark_server_received["body"] = {"code": 400, "message": "bad key"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        try:
            await client.push(BarkPayload(body="x"))
        except BarkAuthError:
            return
    raise AssertionError("expected BarkAuthError")


async def test_push_401_raises_auth_error(client_to, bark_server_received):
    bark_server_received["status"] = 401
    bark_server_received["body"] = {"code": 401, "message": "unauthorized"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        try:
            await client.push(BarkPayload(body="x"))
        except BarkAuthError:
            return
    raise AssertionError("expected BarkAuthError")


async def test_push_429_raises_rate_limit_error(client_to, bark_server_received):
    bark_server_received["status"] = 429
    bark_server_received["body"] = {"code": 429, "message": "rate limited"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        try:
            await client.push(BarkPayload(body="x"))
        except BarkRateLimitError:
            return
    raise AssertionError("expected BarkRateLimitError")


async def test_push_500_raises_server_error(client_to, bark_server_received):
    bark_server_received["status"] = 500
    bark_server_received["body"] = {"code": 500, "message": "boom"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        try:
            await client.push(BarkPayload(body="x"))
        except BarkServerError:
            return
    raise AssertionError("expected BarkServerError")


async def test_push_other_non_200_raises_push_error(client_to, bark_server_received):
    bark_server_received["status"] = 404
    bark_server_received["body"] = {"code": 404, "message": "not found"}
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)
        try:
            await client.push(BarkPayload(body="x"))
        except BarkPushError as err:
            assert err.code == 404
            return
    raise AssertionError("expected BarkPushError")


async def test_push_timeout_raises_connection_error(client_to, bark_server_received):
    bark_server_received["delay"] = 5
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session, timeout=1)
        try:
            await client.push(BarkPayload(body="x"))
        except BarkConnectionError:
            return
    raise AssertionError("expected BarkConnectionError")
```

> 注：`test_push_timeout_raises_connection_error` 需要 conftest handler 支持 delay。下一步会改 conftest。

- [ ] **Step 2: 扩展 `tests/conftest.py` 的 handler 支持 delay 与状态码**

将 conftest 中 `handler` 替换为：

```python
    async def handler(request: web.Request) -> web.Response:
        import asyncio

        bark_server_received["method"] = request.method
        bark_server_received["path"] = request.path
        bark_server_received["headers"] = dict(request.headers)
        try:
            bark_server_received["json"] = await request.json()
        except Exception:
            bark_server_received["json"] = None
        bark_server_received["requests"].append(request.path)
        delay = bark_server_received.get("delay", 0)
        if delay:
            await asyncio.sleep(delay)
        status: int = bark_server_received.get("status", 200)
        body: Any = bark_server_received.get(
            "body", {"code": 200, "message": "success", "timestamp": 1700000000}
        )
        return web.json_response(body, status=status)
```

- [ ] **Step 3: 运行测试验证失败**

Run: `pytest tests/test_bark_api.py -v`
Expected: FAIL — 当前 `push()` 把所有非 200 当 `BarkPushError`，所以 `test_push_400_raises_auth_error` 等会失败（抛出的是 `BarkPushError` 而非 `BarkAuthError`）。超时测试可能也需要确认 `asyncio.TimeoutError` 被捕获（当前只捕 `aiohttp.ClientError`）。

- [ ] **Step 4: 修改 `bark_api.py` 的 `push()` 状态码映射，并捕获超时**

找到 `push` 方法中的这段：

```python
        try:
            async with session.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                text = await resp.text()
        except aiohttp.ClientError as err:
            raise BarkConnectionError(f"failed to reach bark server: {err}") from err
```

替换为：

```python
        import asyncio

        try:
            async with session.post(
                url,
                json=body,
                headers={"Content-Type": "application/json"},
                timeout=aiohttp.ClientTimeout(total=self._timeout),
            ) as resp:
                text = await resp.text()
        except (aiohttp.ClientError, asyncio.TimeoutError) as err:
            raise BarkConnectionError(f"failed to reach bark server: {err}") from err
```

再找到这段（结尾的非 200 处理）：

```python
        if resp.status == 200 and code == 200:
            return BarkResponse(code=code, message=message, timestamp=timestamp)
        raise BarkPushError(code, message or text)
```

替换为：

```python
        if resp.status == 200 and code == 200:
            return BarkResponse(code=code, message=message, timestamp=timestamp)
        if resp.status in (400, 401):
            raise BarkAuthError(f"bark rejected the request ({resp.status}): {message}")
        if resp.status == 429:
            raise BarkRateLimitError("bark rate-limited the request; retry later")
        if 500 <= resp.status < 600:
            raise BarkServerError(f"bark server error ({resp.status}): {message}")
        raise BarkPushError(resp.status, message or text)
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_bark_api.py -v`
Expected: PASS（全部 8 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_bark_api.py tests/conftest.py custom_components/bark/bark_api.py
git commit -m "feat(api): map HTTP status codes to typed Bark errors"
```

---

## Task 6: BarkClient — 加密推送集成

**Files:**
- Modify: `tests/test_bark_api.py`（追加加密集成测试）

> `BarkClient.push()` 在 Task 4 已包含加密分支（`if self._encryption == AES_128_CBC.value`）。本任务只验证端到端加密行为，不新增产品代码。

- [ ] **Step 1: 追加加密集成测试到 `tests/test_bark_api.py`**

```python
import base64

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

ENC_KEY = "1234567890123456"


async def test_encrypted_push_sends_ciphertext_only(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(
            session=session, encryption="aes-128-cbc", encryption_key=ENC_KEY
        )
        await client.push(BarkPayload(body="secret", title="t"))
    sent = bark_server_received["json"]
    assert set(sent.keys()) == {"ciphertext", "iv"}
    # no plaintext fields leak
    assert "body" not in sent and "title" not in sent


async def test_encrypted_push_roundtrip_decrypts(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(
            session=session, encryption="aes-128-cbc", encryption_key=ENC_KEY
        )
        await client.push(BarkPayload(body="secret", title="t"))
    sent = bark_server_received["json"]
    iv_bytes = base64.b64decode(sent["iv"])
    cipher = Cipher(algorithms.AES(ENC_KEY.encode("utf-8")), modes.CBC(iv_bytes))
    decryptor = cipher.decryptor()
    padded = decryptor.update(base64.b64decode(sent["ciphertext"])) + decryptor.finalize()
    unpadder = PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    import json as _json
    decoded = _json.loads(plaintext.decode("utf-8"))
    assert decoded == {"body": "secret", "title": "t"}


async def test_encrypted_push_uses_random_iv(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(
            session=session, encryption="aes-128-cbc", encryption_key=ENC_KEY
        )
        await client.push(BarkPayload(body="a"))
        first_iv = bark_server_received["json"]["iv"]
        await client.push(BarkPayload(body="a"))
        second_iv = bark_server_received["json"]["iv"]
    assert first_iv != second_iv


async def test_no_encryption_when_disabled(client_to, bark_server_received):
    async with aiohttp.ClientSession() as session:
        client = client_to(session=session)  # encryption defaults to "none"
        await client.push(BarkPayload(body="plain"))
    sent = bark_server_received["json"]
    assert "ciphertext" not in sent and "iv" not in sent
    assert sent == {"body": "plain"}
```

- [ ] **Step 2: 运行测试验证通过**

Run: `pytest tests/test_bark_api.py -v`
Expected: PASS（全部 12 个测试）。

> 如果 `test_encrypted_push_roundtrip_decrypts` 失败，说明 client 序列化的 JSON 字段顺序/格式与解密端不兼容。检查 `push()` 里 `json.dumps` 的 `separators` 与 ensure_ascii 设置，确保解码后字段值正确（顺序不影响 JSON 解析）。

- [ ] **Step 3: Commit**

```bash
git add tests/test_bark_api.py
git commit -m "test(api): verify encrypted push end-to-end behavior"
```

---

## Task 7: Config Flow — 用户步骤（含测试推送）

**Files:**
- Create: `tests/test_config_flow.py`
- Create: `custom_components/bark/config_flow.py`
- Create: `custom_components/bark/translations/en.json`
- Create: `custom_components/bark/translations/zh-Hans.json`

- [ ] **Step 1: 写失败测试 `tests/test_config_flow.py`**

```python
"""Tests for the Bark config flow."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant import config_entries
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_ENCRYPTION,
    CONF_ENCRYPTION_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DOMAIN,
)

USER_INPUT = {
    CONF_NAME: "My iPhone",
    CONF_SERVER_URL: "https://api.day.app",
    CONF_DEVICE_KEY: "TESTKEY",
    CONF_ENCRYPTION: "none",
}


async def test_user_flow_success(hass: HomeAssistant):
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "user"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "My iPhone"
    assert result["data"] == USER_INPUT


async def test_user_flow_test_push_fails_shows_error(hass: HomeAssistant):
    from custom_components.bark.bark_api import BarkAuthError

    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(side_effect=BarkAuthError("bad key")),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], USER_INPUT
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"]["base"] == "test_push_failed"


async def test_user_flow_encryption_key_required_when_enabled(hass: HomeAssistant):
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                **USER_INPUT,
                CONF_ENCRYPTION: "aes-128-cbc",
                CONF_ENCRYPTION_KEY: "",
            },
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_encryption_key"
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_config_flow.py -v`
Expected: FAIL — `custom_components.bark.config_flow` 不存在。

- [ ] **Step 3: 创建 `custom_components/bark/config_flow.py`**

```python
"""Config flow for the Bark integration."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.data_entry_flow import FlowResult
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .bark_api import (
    BarkClient,
    BarkEncryptionError,
    BarkError,
    BarkPayload,
    EncryptionAlgorithm,
)
from .const import (
    CONF_DEVICE_KEY,
    CONF_ENCRYPTION,
    CONF_ENCRYPTION_KEY,
    CONF_SERVER_URL,
    DEFAULT_SERVER_URL,
    DOMAIN,
    ENCRYPTION_AES_128_CBC,
    ENCRYPTION_NONE,
)

_ENCRYPTION_OPTIONS = {
    ENCRYPTION_NONE: "Off",
    ENCRYPTION_AES_128_CBC: "AES-128-CBC",
}


def _user_schema() -> vol.Schema:
    return vol.Schema(
        {
            vol.Required(CONF_NAME): str,
            vol.Required(CONF_SERVER_URL, default=DEFAULT_SERVER_URL): str,
            vol.Required(CONF_DEVICE_KEY): str,
            vol.Required(CONF_ENCRYPTION, default=ENCRYPTION_NONE): vol.In(
                _ENCRYPTION_OPTIONS
            ),
            vol.Optional(CONF_ENCRYPTION_KEY): str,
        }
    )


def _validate_encryption_key(user_input: dict[str, Any]) -> str | None:
    if user_input[CONF_ENCRYPTION] == ENCRYPTION_AES_128_CBC:
        key = user_input.get(CONF_ENCRYPTION_KEY) or ""
        if len(key) != 16:
            return "invalid_encryption_key"
    return None


async def _send_test_push(hass, user_input: dict[str, Any]) -> None:
    client = BarkClient(
        server_url=user_input[CONF_SERVER_URL],
        device_key=user_input[CONF_DEVICE_KEY],
        encryption=user_input[CONF_ENCRYPTION],
        encryption_key=user_input.get(CONF_ENCRYPTION_KEY),
        session=async_get_clientsession(hass),
    )
    try:
        await client.push(BarkPayload(title=user_input[CONF_NAME], body="Bark 已接入 Home Assistant"))
    finally:
        await client.async_close()


class BarkConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a Bark config flow."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            err = _validate_encryption_key(user_input)
            if err is None:
                try:
                    await _send_test_push(self.hass, user_input)
                except BarkEncryptionError:
                    err = "invalid_encryption_key"
                except BarkError:
                    err = "test_push_failed"
            if err is None:
                return self.async_create_entry(
                    title=user_input[CONF_NAME], data=user_input
                )
            errors["base"] = err
        return self.async_show_form(
            step_id="user", data_schema=_user_schema(), errors=errors
        )
```

- [ ] **Step 4: 创建 `custom_components/bark/translations/en.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Bark Device",
        "data": {
          "name": "Device name",
          "server_url": "Server URL",
          "device_key": "Device key",
          "encryption": "Encryption",
          "encryption_key": "Encryption key (16 chars)"
        }
      }
    },
    "error": {
      "invalid_encryption_key": "Encryption key must be exactly 16 characters",
      "test_push_failed": "Test push failed; check the server URL, device key and encryption settings"
    },
    "abort": {
      "already_configured": "This Bark device is already configured"
    }
  }
}
```

- [ ] **Step 5: 创建 `custom_components/bark/translations/zh-Hans.json`**

```json
{
  "config": {
    "step": {
      "user": {
        "title": "Bark 设备",
        "data": {
          "name": "设备名称",
          "server_url": "服务器地址",
          "device_key": "设备 Key",
          "encryption": "推送加密",
          "encryption_key": "加密 Key（16 个字符）"
        }
      }
    },
    "error": {
      "invalid_encryption_key": "加密 Key 必须正好是 16 个字符",
      "test_push_failed": "测试推送失败，请检查服务器地址、设备 Key 与加密设置"
    },
    "abort": {
      "already_configured": "该 Bark 设备已配置"
    }
  }
}
```

- [ ] **Step 6: 运行测试验证通过**

Run: `pytest tests/test_config_flow.py -v`
Expected: PASS（3 个测试）。

> 若 `test_user_flow_success` 因 HA 需要 `unique_id` 报错，检查是否漏了 `async_create_entry`。本测试不要求唯一性（未设 unique_id）。

- [ ] **Step 7: Commit**

```bash
git add tests/test_config_flow.py custom_components/bark/config_flow.py custom_components/bark/translations/
git commit -m "feat(config-flow): add user step with test push validation"
```

---

## Task 8: Config Flow — Reconfigure（编辑已配置设备）

**Files:**
- Modify: `tests/test_config_flow.py`（追加 reconfigure 测试）
- Modify: `custom_components/bark/config_flow.py`（追加 `async_step_reconfigure` + `async_step_reconfigure_confirm`）

- [ ] **Step 1: 追加失败测试到 `tests/test_config_flow.py`**

```python
async def test_reconfigure_flow_updates_entry(hass: HomeAssistant):
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={**USER_INPUT},
        unique_id="TESTKEY",
    )
    entry.add_to_hass(hass)

    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        result = await entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "reconfigure"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {**USER_INPUT, CONF_SERVER_URL: "https://custom.example.com"},
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.data[CONF_SERVER_URL] == "https://custom.example.com"
```

> 需要 `MockConfigEntry` 导入。在测试文件顶部加：
```python
from pytest_homeassistant_custom_component.common import MockConfigEntry
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_config_flow.py::test_reconfigure_flow_updates_entry -v`
Expected: FAIL — 没有 `async_step_reconfigure`，流程 abort。

- [ ] **Step 3: 在 `config_flow.py` 追加 reconfigure 步骤**

在 `BarkConfigFlow` 类内追加（`async_step_user` 之后）：

```python
    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Reconfigure an existing entry."""
        return await self.async_step_reconfigure_confirm(user_input)

    async def async_step_reconfigure_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        errors: dict[str, str] = {}
        entry = self._get_reconfigure_entry()
        if user_input is not None:
            err = _validate_encryption_key(user_input)
            if err is None:
                try:
                    await _send_test_push(self.hass, user_input)
                except BarkEncryptionError:
                    err = "invalid_encryption_key"
                except BarkError:
                    err = "test_push_failed"
            if err is None:
                self.hass.config_entries.async_update_entry(
                    entry, data=user_input, title=user_input[CONF_NAME]
                )
                await self.hass.config_entries.async_reload(entry.entry_id)
                return self.async_abort(reason="reconfigure_successful")
            errors["base"] = err

        current = dict(entry.data)
        return self.async_show_form(
            step_id="reconfigure",
            data_schema=_user_schema(),
            errors=errors,
            description_placeholders={"name": current.get(CONF_NAME, "")},
            last_step=True,
        )
```

> 注：`_get_reconfigure_entry()` 是 HA 2024.4+ 提供的基类方法，返回触发 reconfigure 的 entry。表单 schema 复用 `_user_schema()`；HA 会用 `entry.data` 预填默认值，但 `vol.Schema` 默认值在 show_form 时不自动回填——为简化，本计划接受用户重新填全字段。若 HA 版本对预填支持更好，后续可在 `description_placeholders` 增强。

- [ ] **Step 4: 更新翻译文件，加入 `reconfigure` step**

在 `en.json` 和 `zh-Hans.json` 的 `config.step` 下追加（与 `user` 同级）：

`en.json`:
```json
        "reconfigure": {
          "title": "Reconfigure Bark Device",
          "data": {
            "name": "Device name",
            "server_url": "Server URL",
            "device_key": "Device key",
            "encryption": "Encryption",
            "encryption_key": "Encryption key (16 chars)"
          }
        }
```

`zh-Hans.json`:
```json
        "reconfigure": {
          "title": "重新配置 Bark 设备",
          "data": {
            "name": "设备名称",
            "server_url": "服务器地址",
            "device_key": "设备 Key",
            "encryption": "推送加密",
            "encryption_key": "加密 Key（16 个字符）"
          }
        }
```

并在 `abort` 节点追加：
```json
      "reconfigure_successful": "Reconfiguration was successful"
```
（zh-Hans：`"reconfigure_successful": "重新配置成功"`）

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_config_flow.py -v`
Expected: PASS（4 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_config_flow.py custom_components/bark/config_flow.py custom_components/bark/translations/
git commit -m "feat(config-flow): add reconfigure flow to edit existing device"
```

---

## Task 9: `__init__.py` — setup/unload entry + 运行时状态

**Files:**
- Create: `tests/test_init.py`
- Modify: `custom_components/bark/__init__.py`
- Modify: `custom_components/bark/const.py`（加 runtime key 常量）

- [ ] **Step 1: 在 `const.py` 追加 runtime 常量**

在文件末尾追加：

```python
DATA_CLIENTS = "clients"
DATA_RUNTIME = "runtime"
RUNTIME_STATUS = "status"
RUNTIME_TIME = "time"
PLATFORMS = ["button", "sensor"]
```

- [ ] **Step 2: 写失败测试 `tests/test_init.py`**

```python
"""Tests for Bark integration setup."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bark import async_setup_entry, async_unload_entry
from custom_components.bark.bark_api import BarkClient
from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DOMAIN,
)


def _mock_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "iPhone",
            CONF_SERVER_URL: "https://api.day.app",
            CONF_DEVICE_KEY: "TESTKEY",
        },
        unique_id="TESTKEY",
    )


async def test_setup_entry_creates_client_and_platforms(hass: HomeAssistant):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert entry.entry_id in hass.data[DOMAIN][DATA_CLIENTS]
    assert isinstance(
        hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id], BarkClient
    )


async def test_unload_entry_closes_client(hass: HomeAssistant):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "async_close", new=AsyncMock()) as closed:
        ok = await async_unload_entry(hass, entry)
        await hass.async_block_till_done()
    assert ok
    closed.assert_awaited_once()
    assert entry.entry_id not in hass.data[DOMAIN][DATA_CLIENTS]
```

> 注：本任务加载 button/sensor 平台，但平台代码尚未实现。为了让 setup 成功，本任务先在 `__init__.py` 中**不**调用 `async_forward_entry_setups`（下一个任务实现实体后再启用）。下方实现里会以注释占位，测试断言不依赖平台。Task 11/12 实现实体后会回头启用 forward。

- [ ] **Step 3: 运行测试验证失败**

Run: `pytest tests/test_init.py -v`
Expected: FAIL — `custom_components.bark.__init__` 没有 `async_setup_entry`。

- [ ] **Step 4: 替换 `custom_components/bark/__init__.py` 全文**

```python
"""The Bark integration."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .bark_api import BarkClient
from .const import (
    CONF_DEVICE_KEY,
    CONF_ENCRYPTION,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DATA_RUNTIME,
    DOMAIN,
    PLATFORMS,
)

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up a Bark config entry."""
    client = BarkClient(
        server_url=entry.data[CONF_SERVER_URL],
        device_key=entry.data[CONF_DEVICE_KEY],
        encryption=entry.data.get(CONF_ENCRYPTION, "none"),
        encryption_key=entry.data.get("encryption_key"),
        session=None,
    )
    domain_data = hass.data.setdefault(DOMAIN, {})
    clients = domain_data.setdefault(DATA_CLIENTS, {})
    clients[entry.entry_id] = client
    domain_data.setdefault(DATA_RUNTIME, {})[entry.entry_id] = {
        "status": "unknown",
        "time": None,
    }

    # Platforms are enabled in Task 11/12 once entities exist.
    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a Bark config entry."""
    unload_ok = True
    platforms = list(getattr(hass.data.get(DOMAIN, {}).get(DATA_CLIENTS, {}), "keys", lambda: [])())
    # Unload platforms (no-op until forward_entry_setups is enabled).
    if PLATFORMS:
        try:
            unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        except ValueError:
            unloaded = True
        unload_ok = unload_ok and unloaded

    clients = hass.data.get(DOMAIN, {}).get(DATA_CLIENTS, {})
    client: BarkClient | None = clients.pop(entry.entry_id, None)
    if client is not None:
        await client.async_close()
    runtime = hass.data.get(DOMAIN, {}).get(DATA_RUNTIME, {})
    runtime.pop(entry.entry_id, None)
    return unload_ok
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_init.py -v`
Expected: PASS（2 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_init.py custom_components/bark/__init__.py custom_components/bark/const.py
git commit -m "feat(init): setup/unload entry with runtime state and client lifecycle"
```

---

## Task 10: `service.py` — `bark.send` schema + handler + target 解析

**Files:**
- Create: `tests/test_service.py`
- Create: `custom_components/bark/service.py`
- Create: `custom_components/bark/services.yaml`

- [ ] **Step 1: 写失败测试 `tests/test_service.py`**

```python
"""Tests for the bark.send service."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bark.bark_api import BarkAuthError, BarkPayload
from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DOMAIN,
)
from custom_components.bark.service import SERVICE_SCHEMA, build_payload


def _mock_entry(unique="TESTKEY"):
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "iPhone",
            CONF_SERVER_URL: "https://api.day.app",
            CONF_DEVICE_KEY: unique,
        },
        unique_id=unique,
    )


def test_build_payload_basic():
    payload = build_payload({"message": "hi", "title": "t"})
    assert payload.title == "t"
    assert payload.body == "hi"


def test_build_payload_markdown_overrides_message():
    payload = build_payload({"message": "hi", "markdown": "# md"})
    assert payload.body is None
    assert payload.markdown == "# md"


def test_build_payload_all_fields():
    payload = build_payload(
        {
            "message": "b",
            "title": "t",
            "subtitle": "st",
            "markdown": "",
            "level": "critical",
            "volume": 9,
            "badge": 2,
            "call": True,
            "auto_copy": True,
            "copy": "c",
            "sound": "minuet",
            "icon": "https://e/i",
            "image": "https://e/img",
            "group": "g",
            "is_archive": True,
            "ttl": 30,
            "url": "https://e",
            "action": "alert",
            "id": "id1",
            "delete": False,
        }
    )
    assert payload.level == "critical" and payload.volume == 9
    assert payload.call is True
    assert payload.auto_copy is True
    assert payload.is_archive is True


async def _setup_entry(hass: HomeAssistant):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_service_send_calls_client_push(hass: HomeAssistant):
    entry = await _setup_entry(hass)
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock()) as pushed:
        await hass.services.async_call(
            DOMAIN,
            "send",
            {
                "message": "hello",
                "target_entity": entry.entry_id,
            },
            blocking=True,
        )
    pushed.assert_awaited_once()
    sent_payload: BarkPayload = pushed.await_args.args[0]
    assert sent_payload.body == "hello"


async def test_service_send_propagates_error(hass: HomeAssistant):
    entry = await _setup_entry(hass)
    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(
        client, "push", new=AsyncMock(side_effect=BarkAuthError("bad"))
    ):
        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                DOMAIN,
                "send",
                {"message": "hello", "target_entity": entry.entry_id},
                blocking=True,
            )
```

> 说明：为了让测试稳定且独立于 entity registry，本任务的 `bark.send` 用一个自定义字段 `target_entity`（值为 config entry id）作为 target 入口。真实 target 通过 services.yaml 的 selector 绑定到设备实体（Task 12 后），handler 同时支持 `target_entity`（entry_id）与解析后的 `entity_id`/`device_id`。

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_service.py -v`
Expected: FAIL — `custom_components.bark.service` 不存在。

- [ ] **Step 3: 创建 `custom_components/bark/service.py`**

```python
"""The bark.send service."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import voluptuous as vol

from homeassistant.const import ATTR_DEVICE_ID, ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .bark_api import BarkError, BarkPayload
from .const import (
    DATA_CLIENTS,
    DATA_RUNTIME,
    DOMAIN,
    EVENT_PUSH_UPDATE,
    RUNTIME_STATUS,
    RUNTIME_TIME,
    STATUS_FAILED,
    STATUS_SUCCESS,
)

_LOGGER = logging.getLogger(__name__)

FIELD_MESSAGE = "message"

SERVICE_SCHEMA = vol.Schema(
    {
        vol.Required(FIELD_MESSAGE): cv.string,
        vol.Optional("title"): cv.string,
        vol.Optional("subtitle"): cv.string,
        vol.Optional("markdown"): cv.string,
        vol.Optional("level"): vol.In(
            ["critical", "active", "timeSensitive", "passive"]
        ),
        vol.Optional("volume"): vol.All(vol.Coerce(int), vol.Range(min=0, max=10)),
        vol.Optional("badge"): vol.Coerce(int),
        vol.Optional("call"): cv.boolean,
        vol.Optional("auto_copy"): cv.boolean,
        vol.Optional("copy"): cv.string,
        vol.Optional("sound"): cv.string,
        vol.Optional("icon"): cv.string,
        vol.Optional("image"): cv.string,
        vol.Optional("group"): cv.string,
        vol.Optional("is_archive"): cv.boolean,
        vol.Optional("ttl"): vol.Coerce(int),
        vol.Optional("url"): cv.string,
        vol.Optional("action"): vol.In(["alert"]),
        vol.Optional("id"): cv.string,
        vol.Optional("delete"): cv.boolean,
        vol.Optional("target_entity"): cv.string,
        vol.Optional(ATTR_ENTITY_ID): cv.ENTITY_SERVICE_SCHEMA,
        vol.Optional(ATTR_DEVICE_ID): cv.ENTITY_SERVICE_SCHEMA,
    },
    extra=vol.ALLOW_EXTRA,
)


def build_payload(data: dict[str, Any]) -> BarkPayload:
    """Build a BarkPayload from service data."""
    return BarkPayload(
        body=data.get(FIELD_MESSAGE),
        title=data.get("title"),
        subtitle=data.get("subtitle"),
        markdown=data.get("markdown") or None,
        level=data.get("level"),
        volume=data.get("volume"),
        badge=data.get("badge"),
        call=data.get("call"),
        auto_copy=data.get("auto_copy"),
        copy=data.get("copy"),
        sound=data.get("sound"),
        icon=data.get("icon"),
        image=data.get("image"),
        group=data.get("group"),
        is_archive=data.get("is_archive"),
        ttl=data.get("ttl"),
        url=data.get("url"),
        action=data.get("action"),
        id=data.get("id"),
        delete=data.get("delete"),
    )


def _resolve_entry_ids(hass: HomeAssistant, data: dict[str, Any]) -> list[str]:
    """Resolve service target to config entry ids."""
    entry_ids: list[str] = []

    if (target := data.get("target_entity")) :
        # Direct config entry id shortcut.
        if target in hass.data[DOMAIN][DATA_CLIENTS]:
            entry_ids.append(target)

    registry = er.async_get(hass)
    entity_ids: list[str] = list(data.get(ATTR_ENTITY_ID) or [])
    for eid in entity_ids:
        ent = registry.async_get(eid)
        if ent and ent.config_entry_id in hass.data[DOMAIN][DATA_CLIENTS]:
            entry_ids.append(ent.config_entry_id)

    device_ids = data.get(ATTR_DEVICE_ID) or []
    if device_ids:
        from homeassistant.helpers import device_registry as dr

        dreg = dr.async_get(hass)
        for did in device_ids:
            dev = dreg.devices.get(did)
            if not dev:
                continue
            for ceid in dev.config_entries:
                if ceid in hass.data[DOMAIN][DATA_CLIENTS]:
                    entry_ids.append(ceid)

    # Dedupe, preserve order.
    seen: set[str] = set()
    unique: list[str] = []
    for eid in entry_ids:
        if eid not in seen:
            seen.add(eid)
            unique.append(eid)
    return unique


async def _do_push(hass: HomeAssistant, entry_id: str, payload: BarkPayload) -> None:
    """Execute a push for one entry and update runtime state."""
    client = hass.data[DOMAIN][DATA_CLIENTS][entry_id]
    runtime = hass.data[DOMAIN][DATA_RUNTIME][entry_id]
    now = datetime.now(timezone.utc).isoformat()
    try:
        await client.push(payload)
    except BarkError as err:
        runtime[RUNTIME_STATUS] = STATUS_FAILED
        runtime[RUNTIME_TIME] = now
        hass.bus.async_fire(
            EVENT_PUSH_UPDATE,
            {DOMAIN: {entry_id: {RUNTIME_STATUS: STATUS_FAILED, RUNTIME_TIME: now}}},
        )
        raise HomeAssistantError(f"Bark 推送失败: {err}") from err
    runtime[RUNTIME_STATUS] = STATUS_SUCCESS
    runtime[RUNTIME_TIME] = now
    hass.bus.async_fire(
        EVENT_PUSH_UPDATE,
        {DOMAIN: {entry_id: {RUNTIME_STATUS: STATUS_SUCCESS, RUNTIME_TIME: now}}},
    )


async def async_setup_services(hass: HomeAssistant) -> None:
    """Register bark.send (idempotent)."""
    if hass.services.has_service(DOMAIN, "send"):
        return

    async def handle_send(call: ServiceCall) -> None:
        data = dict(call.data)
        entry_ids = _resolve_entry_ids(hass, data)
        if not entry_ids:
            raise HomeAssistantError(
                "bark.send 需要指定目标 Bark 设备（target_entity / entity_id / device_id）"
            )
        payload = build_payload(data)
        for entry_id in entry_ids:
            await _do_push(hass, entry_id, payload)

    hass.services.async_register(
        DOMAIN, "send", handle_send, schema=SERVICE_SCHEMA, supports_response=False
    )
```

- [ ] **Step 4: 创建 `custom_components/bark/services.yaml`**

```yaml
send:
  name: Send Bark push
  description: Send a push notification via Bark with full parameter support.
  target:
    entity:
      integration: bark
      domain: [button, sensor]
  fields:
    message:
      name: Message
      description: Push body text.
      required: true
      example: "Hello"
      selector:
        text: {}
    title:
      name: Title
      selector:
        text: {}
    subtitle:
      name: Subtitle
      selector:
        text: {}
    markdown:
      name: Markdown body
      description: Overrides "message" if set.
      selector:
        text:
          multiline: true
    level:
      name: Level
      selector:
        select:
          options: ["critical", "active", "timeSensitive", "passive"]
    volume:
      name: Volume
      description: Only effective when level=critical (0-10).
      selector:
        number:
          min: 0
          max: 10
          step: 1
    badge:
      name: Badge
      selector:
        number:
          min: 0
          mode: box
    call:
      name: Repeating ringtone
      selector:
        boolean: {}
    auto_copy:
      name: Auto copy
      selector:
        boolean: {}
    copy:
      name: Copy content
      selector:
        text: {}
    sound:
      name: Sound
      selector:
        text: {}
    icon:
      name: Icon URL
      selector:
        text: {}
    image:
      name: Image URL
      selector:
        text: {}
    group:
      name: Group
      selector:
        text: {}
    is_archive:
      name: Archive
      selector:
        boolean: {}
    ttl:
      name: TTL (seconds)
      selector:
        number:
          min: 0
          mode: box
    url:
      name: Click URL
      selector:
        text: {}
    action:
      name: Action
      selector:
        select:
          options: ["alert"]
    id:
      name: Notification ID
      selector:
        text: {}
    delete:
      name: Delete
      selector:
        boolean: {}
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_service.py -v`
Expected: PASS（5 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_service.py custom_components/bark/service.py custom_components/bark/services.yaml
git commit -m "feat(service): add bark.send service with schema and target resolution"
```

---

## Task 11: `entity.py` — 设备 + `button.test_push`

**Files:**
- Create: `tests/test_entity.py`
- Create: `custom_components/bark/entity.py`
- Create: `custom_components/bark/button.py`（注册 button 平台）

- [ ] **Step 1: 写失败测试 `tests/test_entity.py`**

```python
"""Tests for Bark entities."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DOMAIN,
)


def _mock_entry():
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: "iPhone",
            CONF_SERVER_URL: "https://api.day.app",
            CONF_DEVICE_KEY: "TESTKEY",
        },
        unique_id="TESTKEY",
    )


async def _setup(hass: HomeAssistant):
    entry = _mock_entry()
    entry.add_to_hass(hass)
    with patch(
        "custom_components.bark.config_flow.BarkClient.push",
        new=AsyncMock(return_value=None),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_test_push_button_created_and_presses(hass: HomeAssistant):
    entry = await _setup(hass)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    ent_id = registry.async_get_entity_id(
        BUTTON_DOMAIN, DOMAIN, f"{entry.entry_id}_test_push"
    )
    assert ent_id is not None

    from custom_components.bark.const import DATA_CLIENTS

    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock()) as pushed:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            "press",
            {"entity_id": ent_id},
            blocking=True,
        )
        await hass.async_block_till_done()
    pushed.assert_awaited_once()
```

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_entity.py -v`
Expected: FAIL — 没有 button 实体。

- [ ] **Step 3: 创建 `custom_components/bark/entity.py`（设备 + 共用基类）**

```python
"""Bark entities and device binding."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_DEVICE_KEY, DOMAIN


def _device_ident(device_key: str) -> str:
    """Stable, non-revealing device identifier (SHA-256 truncated)."""
    return hashlib.sha256(device_key.encode("utf-8")).hexdigest()[:16]


def build_device_info(entry: ConfigEntry) -> DeviceInfo:
    return DeviceInfo(
        identifiers={(DOMAIN, _device_ident(entry.data[CONF_DEVICE_KEY]))},
        name=entry.data.get(CONF_NAME, "Bark"),
        manufacturer="Bark",
        model="Bark Device",
        sw_version="1.0.0",
    )


class BarkEntity(Entity):
    """Base entity that binds to a Bark device."""

    _attr_has_entity_name = True

    def __init__(self, entry: ConfigEntry) -> None:
        self._entry = entry
        self._attr_device_info = build_device_info(entry)
```

- [ ] **Step 4: 创建 `custom_components/bark/button.py`（button 平台）**

```python
"""Bark button platform (test push)."""

from __future__ import annotations

import logging

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .bark_api import BarkPayload
from .const import DATA_CLIENTS, DOMAIN
from .entity import BarkEntity

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([BarkTestPushButton(hass, entry)])


class BarkTestPushButton(BarkEntity, ButtonEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(entry)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_test_push"
        self._attr_name = "Test push"
        self._attr_icon = "mdi:bell"

    async def async_press(self) -> None:
        from .service import _do_push

        client = self._hass.data[DOMAIN][DATA_CLIENTS][self._entry.entry_id]
        await _do_push(
            self._hass,
            self._entry.entry_id,
            BarkPayload(
                title=self._entry.data.get(CONF_NAME, "Bark"),
                body="Home Assistant 测试推送",
            ),
        )


from homeassistant.const import CONF_NAME  # noqa: E402  (kept near use)
```

> 注：`from .service import _do_push` 放在方法内部避免循环导入（service.py 与 button.py 可能互相引用）。

- [ ] **Step 5: 启用 button 平台 — 修改 `__init__.py`**

找到：
```python
    # Platforms are enabled in Task 11/12 once entities exist.
    # await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```
替换为：
```python
    await hass.config_entries.async_forward_entry_setups(
        entry, [p for p in PLATFORMS if p == "button"]
    )
    return True
```

并在 `__init__.py` 顶部 import 之后注册服务。找到 `_LOGGER = logging.getLogger(__name__)` 之后追加：

```python
from .service import async_setup_services  # noqa: E402
```

并在 `async_setup_entry` return True 之前，确保服务注册（每个 entry setup 都调用，函数内部幂等）。在 `await hass.config_entries.async_forward_entry_setups(...)` 之后、`return True` 之前追加：

```python
    await async_setup_services(hass)
```

- [ ] **Step 6: 运行测试验证通过**

Run: `pytest tests/test_entity.py tests/test_init.py -v`
Expected: PASS。

> 如果 `test_test_push_button_created_and_presses` 因 unique_id 形态不匹配而 `ent_id is None`，检查 button 的 `_attr_unique_id` 与测试里的 `f"{entry.entry_id}_test_push"` 一致。

- [ ] **Step 7: Commit**

```bash
git add tests/test_entity.py custom_components/bark/entity.py custom_components/bark/button.py custom_components/bark/__init__.py
git commit -m "feat(entity): add device binding and test push button"
```

---

## Task 12: `entity.py` — 诊断 sensors（status / time）

**Files:**
- Modify: `tests/test_entity.py`（追加 sensor 测试）
- Create: `custom_components/bark/sensor.py`
- Modify: `custom_components/bark/__init__.py`（启用 sensor 平台）

- [ ] **Step 1: 追加 sensor 测试到 `tests/test_entity.py`**

```python
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util


async def test_sensors_created_with_unknown_initial_state(hass: HomeAssistant):
    entry = await _setup(hass)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    status_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_status"
    )
    time_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_time"
    )
    assert status_id is not None
    assert time_id is not None
    assert hass.states.get(status_id).state == "unknown"


async def test_sensor_status_updates_to_success_after_send(hass: HomeAssistant):
    entry = await _setup(hass)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    status_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_status"
    )
    from custom_components.bark.const import DATA_CLIENTS

    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(client, "push", new=AsyncMock()):
        await hass.services.async_call(
            DOMAIN,
            "send",
            {"message": "x", "target_entity": entry.entry_id},
            blocking=True,
        )
        await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "success"


async def test_sensor_status_updates_to_failed_on_error(hass: HomeAssistant):
    entry = await _setup(hass)
    await hass.async_block_till_done()
    registry = er.async_get(hass)
    status_id = registry.async_get_entity_id(
        SENSOR_DOMAIN, DOMAIN, f"{entry.entry_id}_last_push_status"
    )
    from custom_components.bark.bark_api import BarkAuthError
    from custom_components.bark.const import DATA_CLIENTS

    client = hass.data[DOMAIN][DATA_CLIENTS][entry.entry_id]
    with patch.object(
        client, "push", new=AsyncMock(side_effect=BarkAuthError("bad"))
    ):
        from homeassistant.exceptions import HomeAssistantError

        try:
            await hass.services.async_call(
                DOMAIN,
                "send",
                {"message": "x", "target_entity": entry.entry_id},
                blocking=True,
            )
        except HomeAssistantError:
            pass
        await hass.async_block_till_done()
    assert hass.states.get(status_id).state == "failed"
```

确保测试文件顶部已有 `from custom_components.bark.const import ... DOMAIN`，并补 `DATA_CLIENTS` 导入（如未在顶部）。在文件顶部 import 区追加：

```python
from custom_components.bark.const import (
    CONF_DEVICE_KEY,
    CONF_NAME,
    CONF_SERVER_URL,
    DATA_CLIENTS,
    DOMAIN,
)
```
（若 `DATA_CLIENTS` 已在测试内局部 import，统一移到顶部即可。）

- [ ] **Step 2: 运行测试验证失败**

Run: `pytest tests/test_entity.py -v`
Expected: FAIL — 没有 sensor 实体。

- [ ] **Step 3: 创建 `custom_components/bark/sensor.py`**

```python
"""Bark sensor platform (diagnostic sensors)."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_event

from .const import DOMAIN, EVENT_PUSH_UPDATE, RUNTIME_STATUS, RUNTIME_TIME
from .entity import BarkEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([BarkLastPushStatusSensor(hass, entry), BarkLastPushTimeSensor(hass, entry)])


class _BarkSensorBase(BarkEntity, SensorEntity):
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, suffix: str) -> None:
        super().__init__(entry)
        self._hass = hass
        self._attr_unique_id = f"{entry.entry_id}_{suffix}"

    @property
    def _runtime(self) -> dict:
        from .const import DATA_RUNTIME

        return self._hass.data[DOMAIN][DATA_RUNTIME][self._entry.entry_id]

    async def async_added_to_hass(self) -> None:
        self.async_on_remove(
            async_track_event(
                self._hass,
                EVENT_PUSH_UPDATE,
                self._on_push_update,
            )
        )

    @callback
    def _on_push_update(self, event: Event) -> None:
        payload = event.data.get(DOMAIN, {})
        if self._entry.entry_id not in payload:
            return
        self.async_write_ha_state()


class BarkLastPushStatusSensor(_BarkSensorBase):
    _attr_icon = "mdi:check-circle-outline"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "last_push_status")
        self._attr_name = "Last push status"

    @property
    def native_value(self) -> str | None:
        return self._runtime.get(RUNTIME_STATUS)


class BarkLastPushTimeSensor(_BarkSensorBase):
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        super().__init__(hass, entry, "last_push_time")
        self._attr_name = "Last push time"
        self._attr_icon = "mdi:clock-outline"

    @property
    def native_value(self) -> datetime | None:
        value = self._runtime.get(RUNTIME_TIME)
        if value is None:
            return None
        from homeassistant.util import dt as dt_util

        return dt_util.parse_datetime(value)
```

- [ ] **Step 4: 启用 sensor 平台 — 修改 `__init__.py`**

找到（Task 11 改后的）：
```python
    await hass.config_entries.async_forward_entry_setups(
        entry, [p for p in PLATFORMS if p == "button"]
    )
    return True
```
替换为：
```python
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True
```

- [ ] **Step 5: 运行测试验证通过**

Run: `pytest tests/test_entity.py -v`
Expected: PASS（全部 4 个测试）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_entity.py custom_components/bark/sensor.py custom_components/bark/__init__.py
git commit -m "feat(entity): add last push status/time diagnostic sensors"
```

---

## Task 13: 设备脱敏 + diagnostics

**Files:**
- Modify: `tests/test_entity.py`（追加 diagnostics 测试）
- Modify: `custom_components/bark/entity.py`（加 diagnostics + redact）

- [ ] **Step 1: 追加测试到 `tests/test_entity.py`**

```python
async def test_device_registry_uses_hashed_identifier(hass: HomeAssistant):
    entry = await _setup(hass)
    await hass.async_block_till_done()
    from homeassistant.helpers import device_registry as dr

    dreg = dr.async_get(hass)
    devices = dr.async_entries_for_config_entry(dreg, entry.entry_id)
    assert len(devices) == 1
    ident = list(devices[0].identifiers)[0]
    assert ident[0] == DOMAIN
    # identifier must NOT be the raw device key
    assert ident[1] != "TESTKEY"
    assert len(ident[1]) == 16
```

- [ ] **Step 2: 运行测试验证通过（redact 已在 entity.py 实现于 Task 11）**

Run: `pytest tests/test_entity.py::test_device_registry_uses_hashed_identifier -v`
Expected: PASS（设备标识在 Task 11 已用 SHA-256 截断，不含原始 key）。

- [ ] **Step 3: 追加 `redact_key` 辅助函数与 diagnostics dump 到 `entity.py`**

在 `entity.py` 末尾追加：

```python
def redact_key(key: str | None) -> str:
    """Redact a device key for logging: show first 4 + last 4."""
    if not key:
        return "<none>"
    if len(key) <= 8:
        return "<redacted>"
    return f"{key[:4]}***{key[-4:]}"
```

> diagnostics dump（HA 的 `diagnostics` 平台）作为可选增强，spec 中已标明初版不实现。本任务只补 redact 工具，日志里使用。

- [ ] **Step 4: 在 `service.py` 的 `_do_push` 错误日志里使用 redact（可选增强）**

找到 `service.py` 中 `_do_push` 的 `except BarkError as err:` 块，在 `raise HomeAssistantError(...)` 之前追加 debug 日志：

```python
        from .entity import redact_key

        _LOGGER.debug(
            "bark push failed for entry %s (key=%s): %s",
            entry_id,
            redact_key(hass.data[DOMAIN][DATA_CLIENTS][entry_id]._device_key),
            err,
        )
```

- [ ] **Step 5: 运行全部测试验证无回归**

Run: `pytest -v`
Expected: PASS（全部）。

- [ ] **Step 6: Commit**

```bash
git add tests/test_entity.py custom_components/bark/entity.py custom_components/bark/service.py
git commit -m "feat(entity): add key redaction helper and hashed device identifiers"
```

---

## Task 14: 收尾 — 顶部 import 整理、README、info.md 完善、HACS 校验

**Files:**
- Modify: `custom_components/bark/bark_api.py`（把末尾追加的 import 移到顶部）
- Modify: `README.md`
- Modify: `info.md`

- [ ] **Step 1: 整理 `bark_api.py` 的 import 到顶部**

把 Task 4 末尾追加的 `import json` 和 `import aiohttp` 移到文件顶部的 import 区。最终顶部 import 区应为：

```python
"""Bark API client and data types."""

from __future__ import annotations

import base64
import json
import logging
import os
from dataclasses import dataclass
from enum import Enum
from typing import Any

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

_LOGGER = logging.getLogger(__name__)
```

删除文件末尾的重复 `import json` / `import aiohttp` 行。删除 `push()` 内部的局部 `import asyncio`，改为在顶部加 `import asyncio`（如果还没加）。

- [ ] **Step 2: 完善 `README.md`**

```markdown
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
```

- [ ] **Step 3: 完善 `info.md`**

```markdown
# Bark

通过 [Bark](https://bark.day.app) 向 iPhone/iPad 发送推送通知。

## 功能

- 多设备：每台 iPhone/iPad 一个 config entry
- 自定义服务器（默认 api.day.app，支持自建 bark-server）
- 端到端 AES-128-CBC 加密
- 独立 `bark.send` 服务，覆盖 Bark 全部推送参数
- 配置时自动测试推送；`button.test_push` 随时测试
- 诊断传感器：最近推送状态/时间
```

- [ ] **Step 4: 运行全套测试 + 语法检查**

Run:
```bash
python -m compileall custom_components/bark
pytest -v
```
Expected: compile 无错；全部测试 PASS。

- [ ] **Step 5: 用 HA 的 hassfest 校验 manifest（可选但推荐）**

Run:
```bash
python - <<'PY'
import json, pathlib
m = json.loads(pathlib.Path("custom_components/bark/manifest.json").read_text())
required = {"domain","name","config_flow","requirements","codeowners","iot_class","version"}
assert required.issubset(m.keys()), m
assert m["domain"] == "bark"
print("manifest OK")
PY
```
Expected: `manifest OK`

- [ ] **Step 6: Commit**

```bash
git add custom_components/bark/bark_api.py README.md info.md
git commit -m "chore: finalize imports, docs and manifest validation"
```

---

## 自检（writing-plans skill 要求）

**1. Spec 覆盖检查** — 对照 spec 各节：
- §3 Config Flow → Task 7（user）+ Task 8（reconfigure）✅
- §4 BarkClient → Task 2（payload）+ Task 4（成功）+ Task 5（错误）+ Task 6（加密集成）✅
- §5 bark.send 服务 → Task 10 ✅（20 字段全部覆盖于 schema + services.yaml）
- §6 实体 → Task 11（button + device）+ Task 12（sensors）✅
- §7 加密细节 → Task 3（原语 + doc 硬约束）+ Task 6（client 集成）✅
- §8 错误处理与日志 → Task 5（错误分层）+ Task 13（redact）✅
- §9 测试策略 → 每个 Task 内 TDD；加密硬约束测试在 Task 3 ✅
- §11 依赖 → Task 1（无额外 requirements，用 HA 内置库）✅

**2. 占位符扫描** — 计划中明确需用户替换的只有 manifest.json 的 GitHub 用户名（已注明）。无 `TODO`/`TBD`/「类似前述」等占位。

**3. 类型一致性** —
- `BarkPayload` 字段名在 Task 2 定义，Task 10 `build_payload` 全部对齐 ✅
- `BarkClient.__init__` 签名 Task 4/7/9 一致 ✅
- 错误类名 Task 3 定义 → Task 5 映射 → Task 7/10 引用一致 ✅
- `hass.data[DOMAIN][DATA_CLIENTS][entry_id]` / `[DATA_RUNTIME]` 结构在 Task 9/10/11/12 一致 ✅
- runtime 字典 key：Task 9 定义 `status`/`time`（字面量），Task 10/12 用 `RUNTIME_STATUS`/`RUNTIME_TIME` 常量 → Task 9 Step 1 已追加这些常量，一致 ✅

**实现时注意点（spec §12）**：
- 加密 key 派生必须通过 Task 3 的 doc 硬约束测试验证；若失败，调研 Bark App 实际派生方式并修正 `encrypt_payload`，不可跳过。
