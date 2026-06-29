from homeassistant.const import Platform

DOMAIN = "ninebot"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BUSINESS_UID = "business_uid"
CONF_AMAP_API_KEY = "amap_api_key"
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 120
API_TIMEOUT = 30
NINEBOT_STORAGE_DIR = "ninebot"
NINECLI_MODULE = "ninecli"
PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
)
