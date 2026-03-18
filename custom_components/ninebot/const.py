from homeassistant.const import Platform

DOMAIN = "ninebot"
CONF_API_KEY = "api_key"
CONF_POLL_INTERVAL = "poll_interval"
DEFAULT_POLL_INTERVAL = 300
BASE_URL = "https://cn-cbu-gateway.ninebot.com"
API_TIMEOUT = 30
PLATFORMS: tuple[Platform, ...] = (
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
)
