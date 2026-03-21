from homeassistant.const import Platform

DOMAIN = "ninebot"
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_ACCESS_TOKEN = "access_token"
CONF_REFRESH_TOKEN = "refresh_token"
CONF_ACCESS_TOKEN_VALIDITY = "access_token_validity"
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 120
API_TIMEOUT = 30
LOGIN_BASE_URL = "https://api-passport-bj.ninebot.com"
LOGIN_PATH = "/v3/openClaw/user/login"
DEVICE_BASE_URL = "https://cn-cbu-gateway.ninebot.com"
DEVICE_LIST_PATH = "/app-api/inner/device/ai/get-device-list"
DEVICE_DYNAMIC_PATH = "/app-api/inner/device/ai/get-device-dynamic-info"
CLIENT_ID = "open_claw_client"
DEFAULT_LANGUAGE = "zh"
PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
)
