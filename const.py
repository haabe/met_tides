DOMAIN = "met_tides"
CONF_HARBOR = "harbor"
CONF_SENSORS = "sensors"
DEFAULT_NAME = "MET Tides"
# MET Norway's terms of service require an identifying User-Agent with contact
# info; generic or browser-like agents may be throttled or blocked.
USER_AGENT = "met_tides/1.1.2 https://github.com/haabe/met_tides"

API_BASE = "https://api.met.no/weatherapi/tidalwater/1.1"
FORECAST_URL = f"{API_BASE}/"
AVAILABLE_URL = f"{API_BASE}/available"

# Harbors listed in the API documentation; offered when the available
# endpoint can't be reached so setup isn't blocked by a transient outage.
DOCUMENTED_HARBORS = [
    "andenes", "bergen", "bodø", "bruravik", "bøfjorden", "ekofisk", "eydehavn",
    "hammerfest", "harstad", "heidrun", "heimsjø", "helgeroa", "honningsvåg",
    "kabelvåg", "kaupanger", "kristiansund", "leirvik", "mausund", "måløy",
    "narvik", "ny-ålesund", "oscarsborg", "oslo", "rørvik", "sandnes", "sirevåg",
    "solumstrand", "stavanger", "tregde", "tromsø", "trondheim", "træna",
    "vardø", "viker", "ålesund",
]  # fmt: skip
REQUEST_TIMEOUT = 10

SENSOR_TYPES = {
    "next_high": "Next High Tide",
    "next_low": "Next Low Tide",
    "current_height": "Current Water Height",
}
