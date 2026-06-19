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

DATA_CLIENTS = "clients"
DATA_RUNTIME = "runtime"
RUNTIME_STATUS = "status"
RUNTIME_TIME = "time"
PLATFORMS = ["button", "sensor"]
