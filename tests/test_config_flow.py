"""Config flow tests."""

import aiohttp
import pytest
from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.met_tides.config_flow import parse_harbors
from custom_components.met_tides.const import DOCUMENTED_HARBORS, DOMAIN

AVAILABLE_URL = "https://api.met.no/weatherapi/tidalwater/1.1/available"


@pytest.fixture(autouse=True)
def no_setup(monkeypatch):
    """Don't run entry setup (and its network call) when a flow creates an entry."""

    async def _ok(*_):
        return True

    monkeypatch.setattr("custom_components.met_tides.async_setup_entry", _ok)


def test_parse_harbors(harbors_xml):
    assert parse_harbors(harbors_xml) == {"oslo": "Oslo", "bergen": "Bergen", "trondheim": "Trondheim"}


def test_parse_harbors_empty_document():
    assert parse_harbors("<available/>") == {}


async def test_user_flow_creates_entry(hass, aioclient_mock, harbors_xml):
    aioclient_mock.get(AVAILABLE_URL, text=harbors_xml)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "Home", "harbor": "bergen", "sensors": ["next_high"]}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Home"
    assert result["data"] == {"name": "Home", "harbor": "bergen", "sensors": ["next_high"]}
    assert result["result"].unique_id == "bergen"


async def test_harbor_must_be_from_list(hass, aioclient_mock, harbors_xml):
    aioclient_mock.get(AVAILABLE_URL, text=harbors_xml)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    schema = result["data_schema"]
    with pytest.raises(Exception, match="value must be one of"):
        schema({"name": "x", "harbor": "atlantis"})


async def test_duplicate_harbor_aborts(hass, aioclient_mock, harbors_xml):
    MockConfigEntry(domain=DOMAIN, unique_id="oslo", data={"harbor": "oslo"}).add_to_hass(hass)
    aioclient_mock.get(AVAILABLE_URL, text=harbors_xml)

    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "x", "harbor": "oslo"})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


def _harbor_options(result) -> dict:
    return result["data_schema"].schema["harbor"].container


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"status": 500},
        {"status": 503, "text": "<available/>"},
        {"exc": aiohttp.ClientError()},
        {"exc": TimeoutError()},
        {"text": "<not xml"},
        {"text": "<available/>"},
    ],
)
async def test_harbor_fetch_failure_falls_back_to_documented_list(hass, aioclient_mock, mock_kwargs):
    aioclient_mock.get(AVAILABLE_URL, **mock_kwargs)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    options = _harbor_options(result)
    assert set(options) == set(DOCUMENTED_HARBORS)
    assert options["tromsø"] == "Tromsø"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "x", "harbor": "tromsø"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == "tromsø"


async def test_harbor_fetch_error_status_ignores_body(hass, aioclient_mock, harbors_xml):
    """A 5xx must not be parsed even if its body looks valid."""
    aioclient_mock.get(AVAILABLE_URL, status=503, text=harbors_xml)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": config_entries.SOURCE_USER})
    assert set(_harbor_options(result)) == set(DOCUMENTED_HARBORS)


def test_documented_harbors_are_normalised():
    assert len(DOCUMENTED_HARBORS) == len(set(DOCUMENTED_HARBORS))
    assert all(h == h.lower().strip() for h in DOCUMENTED_HARBORS)
