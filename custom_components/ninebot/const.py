from homeassistant.const import Platform

DOMAIN = "ninebot"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_BUSINESS_UID = "business_uid"
CONF_KEEP_LAST_DATA_ON_ERROR = "keep_last_data_on_error"
CONF_POLL_INTERVAL = "poll_interval"
CONF_REQUEST_DELAY = "request_delay"
CONF_DEVICE_DELAY = "device_delay"
DEFAULT_POLL_INTERVAL = 120
DEFAULT_REQUEST_DELAY = 0
DEFAULT_DEVICE_DELAY = 0
API_TIMEOUT = 30
NINEBOT_STORAGE_DIR = "ninebot"
NINECLI_MODULE = "ninecli"
PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.DEVICE_TRACKER,
    Platform.BUTTON,
    Platform.LOCK,
)
