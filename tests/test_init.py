"""Integration tests: setup, sensors, update failures, unload."""

from datetime import timedelta

import aiohttp
import pytest
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.met_tides.const import DOMAIN, USER_AGENT
from tide_helpers import M2_PERIOD

FORECAST_URL = "https://api.met.no/weatherapi/tidalwater/1.1/"

HIGH = "sensor.tides_oslo_next_high"
LOW = "sensor.tides_oslo_next_low"
HEIGHT = "sensor.tides_oslo_current_height"


@pytest.fixture
def entry() -> MockConfigEntry:
    return MockConfigEntry(
        domain=DOMAIN,
        title="MET Tides",
        unique_id="oslo",
        data={"name": "MET Tides", "harbor": "oslo", "sensors": ["next_high", "next_low", "current_height"]},
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> bool:
    entry.add_to_hass(hass)
    result = await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    return result


async def test_setup_creates_sensors(
    hass, entry, aioclient_mock: AiohttpClientMocker, forecast_text, freezer, forecast_start
):
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)

    assert await _setup(hass, entry)
    assert entry.state is ConfigEntryState.LOADED

    high = hass.states.get(HIGH)
    low = hass.states.get(LOW)
    height = hass.states.get(HEIGHT)
    assert high.attributes["device_class"] == "timestamp"
    assert high.attributes["harbor"] == "Oslo"
    assert high.attributes["height_m"] == pytest.approx(1.0, abs=0.01)
    assert low.attributes["height_m"] == pytest.approx(-1.0, abs=0.01)
    assert high.state < low.state  # ISO-8601 sorts chronologically
    assert float(height.state) == pytest.approx(0.0, abs=0.01)
    assert height.attributes["unit_of_measurement"] == "m"

    # One request, with an identifying User-Agent as required by MET's ToS
    assert aioclient_mock.call_count == 1
    headers = aioclient_mock.mock_calls[0][3]
    assert headers["User-Agent"] == USER_AGENT
    assert "Mozilla" not in USER_AGENT


async def test_unique_ids_are_stable(hass, entry, aioclient_mock, forecast_text, freezer, forecast_start):
    """Changing unique_id format would orphan users' existing entities."""
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    await _setup(hass, entry)
    registry = er.async_get(hass)
    assert registry.async_get(HIGH).unique_id == "met_tides_oslo_next_high"
    assert registry.async_get(LOW).unique_id == "met_tides_oslo_next_low"
    assert registry.async_get(HEIGHT).unique_id == "met_tides_oslo_current_height"


async def test_only_selected_sensors_created(hass, aioclient_mock, forecast_text, freezer, forecast_start):
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    entry = MockConfigEntry(domain=DOMAIN, data={"name": "x", "harbor": "oslo", "sensors": ["next_low"]})
    await _setup(hass, entry)
    assert hass.states.get(LOW) is not None
    assert hass.states.get(HIGH) is None
    assert hass.states.get(HEIGHT) is None


@pytest.mark.parametrize(
    "mock_kwargs",
    [
        {"status": 500},
        {"status": 403},
        {"exc": aiohttp.ClientError()},
        {"exc": TimeoutError()},
        {"text": "garbage with no data rows"},
    ],
)
async def test_first_refresh_failure_retries_setup(hass, entry, aioclient_mock, mock_kwargs):
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, **mock_kwargs)
    assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_later_failure_marks_unavailable_then_recovers(
    hass, entry, aioclient_mock, forecast_text, freezer, forecast_start
):
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    await _setup(hass, entry)
    assert hass.states.get(HIGH).state != STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, status=503)
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    for entity_id in (HIGH, LOW, HEIGHT):
        assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    aioclient_mock.clear_requests()
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(HIGH).state != STATE_UNAVAILABLE


async def test_current_height_updates_between_fetches(
    hass, entry, aioclient_mock, forecast_text, freezer, forecast_start
):
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    await _setup(hass, entry)
    before = float(hass.states.get(HEIGHT).state)

    # Well inside the hourly fetch interval: height must move, no new request
    freezer.tick(timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    after = float(hass.states.get(HEIGHT).state)
    assert after > before
    assert aioclient_mock.call_count == 1


async def test_next_tide_rolls_over_after_it_passes(
    hass, entry, aioclient_mock, forecast_text, freezer, forecast_start
):
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    await _setup(hass, entry)
    first_high = hass.states.get(HIGH).state

    freezer.move_to(forecast_start + M2_PERIOD / 4 + timedelta(minutes=30))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert hass.states.get(HIGH).state > first_high


async def test_unload(hass, entry, aioclient_mock, forecast_text, freezer, forecast_start):
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, text=forecast_text)
    await _setup(hass, entry)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.NOT_LOADED
    assert hass.states.get(HIGH).state == STATE_UNAVAILABLE


async def test_error_status_with_parseable_body_is_rejected(hass, entry, aioclient_mock, forecast_text):
    """A 4xx/5xx must not be parsed as data even if its body looks valid."""
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, status=429, text=forecast_text)
    assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_non_ascii_harbor(hass, aioclient_mock, forecast_text, freezer, forecast_start):
    """Several documented harbors (tromsø, ålesund, bodø, ...) are non-ASCII."""
    freezer.move_to(forecast_start)
    aioclient_mock.get(FORECAST_URL, params={"harbor": "ålesund"}, text=forecast_text)
    entry = MockConfigEntry(domain=DOMAIN, unique_id="ålesund", data={"name": "x", "harbor": "ålesund"})
    assert await _setup(hass, entry)
    assert aioclient_mock.call_count == 1

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id("sensor", DOMAIN, "met_tides_ålesund_next_high")
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state.attributes["harbor"] == "Ålesund"
    assert state.attributes["friendly_name"] == "Tides Ålesund Next High"


@pytest.mark.parametrize("status", [400, 404, 422])
async def test_withdrawn_harbor_gives_actionable_error(hass, entry, aioclient_mock, caplog, status):
    """MET can drop harbors without notice; the log should say what to do."""
    aioclient_mock.get(FORECAST_URL, params={"harbor": "oslo"}, status=status)
    assert not await _setup(hass, entry)
    assert entry.state is ConfigEntryState.SETUP_RETRY
    assert "may have been withdrawn" in caplog.text
