import logging
import aiohttp
import xml.etree.ElementTree as ET
import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .const import DOMAIN, CONF_HARBOR, CONF_SENSORS, SENSOR_TYPES, DEFAULT_NAME, USER_AGENT

_LOGGER = logging.getLogger(__name__)
async def fetch_harbors(hass):
    """Fetch available harbors from MET API."""
    url = "https://api.met.no/weatherapi/tidalwater/1.1/available.xml"
    headers = {"User-Agent": USER_AGENT}
    try:
        session = async_get_clientsession(hass)
        async with session.get(url, headers=headers) as resp:
            text = await resp.text()
            _LOGGER.debug("Raw harbor XML: %s", text)
            root = ET.fromstring(text)
            harbors = {}
            for query in root.findall("query"):
                for param in query.findall("parameter"):
                    name = param.findtext("name")
                    value = param.findtext("value")
                    if name == "harbor":
                        harbors[value] = value.capitalize()
            _LOGGER.debug("Parsed harbors: %s", harbors)
            return harbors
    except Exception as e:
        _LOGGER.error("Error fetching harbor list: %s", e)
        return {}


class METTidesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step when user adds the integration."""
        if user_input is not None:
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        # Fetch harbors for dropdown
        harbors = await fetch_harbors(self.hass)
        if not harbors:
            harbors = {"": "No harbors available"}

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default="MET Tides"): str,
                vol.Required(CONF_HARBOR): vol.In(harbors),
                vol.Optional(
                    CONF_SENSORS, default=["next_high", "next_low", "current_height"]
                ): cv.multi_select(SENSOR_TYPES),
            }
        )

        return self.async_show_form(
            step_id="user",
            data_schema=schema,
        )