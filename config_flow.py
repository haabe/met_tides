import logging
import xml.etree.ElementTree as ET

import aiohttp
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import (
    AVAILABLE_URL,
    CONF_HARBOR,
    CONF_SENSORS,
    DEFAULT_NAME,
    DOMAIN,
    REQUEST_TIMEOUT,
    SENSOR_TYPES,
    USER_AGENT,
)

_LOGGER = logging.getLogger(__name__)


def parse_harbors(text: str) -> dict:
    """Parse the MET available document into {harbor_id: label}."""
    root = ET.fromstring(text)
    harbors = {}
    for query in root.findall("query"):
        for param in query.findall("parameter"):
            value = param.findtext("value")
            if param.findtext("name") == "harbor" and value:
                harbors[value] = value.capitalize()
    return harbors


async def fetch_harbors(hass) -> dict:
    """Fetch available harbors from MET API. Returns {} on any failure."""
    headers = {"User-Agent": USER_AGENT}
    try:
        session = async_get_clientsession(hass)
        async with session.get(
            AVAILABLE_URL, headers=headers, timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
        ) as resp:
            resp.raise_for_status()
            text = await resp.text()
        harbors = parse_harbors(text)
    except (TimeoutError, aiohttp.ClientError, ET.ParseError) as e:
        _LOGGER.error("Error fetching harbor list: %s", e)
        return {}
    _LOGGER.debug("Parsed harbors: %s", harbors)
    return harbors


class METTidesConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        """Handle the initial step when user adds the integration."""
        if user_input is not None:
            await self.async_set_unique_id(user_input[CONF_HARBOR].lower())
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=user_input[CONF_NAME],
                data=user_input,
            )

        harbors = await fetch_harbors(self.hass)
        if not harbors:
            # MET's harbor list is dynamic (API changelog 2026-09-11), so there
            # is no safe static fallback
            return self.async_abort(reason="cannot_connect")

        schema = vol.Schema(
            {
                vol.Required(CONF_NAME, default=DEFAULT_NAME): str,
                vol.Required(CONF_HARBOR): vol.In(dict(sorted(harbors.items()))),
                vol.Optional(CONF_SENSORS, default=list(SENSOR_TYPES)): cv.multi_select(SENSOR_TYPES),
            }
        )

        return self.async_show_form(step_id="user", data_schema=schema)
