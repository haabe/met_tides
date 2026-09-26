import logging
from datetime import UTC, datetime, timedelta

import aiohttp
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import callback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity, UpdateFailed

from .const import FORECAST_URL, REQUEST_TIMEOUT, USER_AGENT

_LOGGER = logging.getLogger(__name__)

DEFAULT_SENSORS = ["next_high", "next_low", "current_height"]
# How often current_height is re-interpolated between hourly API fetches
CURRENT_HEIGHT_REFRESH = timedelta(minutes=5)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MET Tides sensors via config entry."""
    harbor = entry.data["harbor"].capitalize()
    coordinator = entry.runtime_data

    # Prefer options over initial data
    sensors = entry.options.get("sensors") or entry.data.get("sensors", DEFAULT_SENSORS)

    async_add_entities(METTideSensor(coordinator, harbor, s) for s in sensors)


async def fetch_tides(session: aiohttp.ClientSession, harbor: str) -> dict:
    """Fetch and parse the tide forecast. Raises UpdateFailed on any failure."""
    headers = {"User-Agent": USER_AGENT}
    _LOGGER.info("Fetching tide data for %s", harbor)
    try:
        async with session.get(
            FORECAST_URL,
            params={"harbor": harbor.lower()},
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT),
        ) as resp:
            resp.raise_for_status()
            text = await resp.text()
    except (TimeoutError, aiohttp.ClientError) as err:
        raise UpdateFailed(f"Error fetching tides for {harbor}: {err}") from err

    _LOGGER.debug("Raw tide data: %s", text[:1000])
    data = parse_tides(text)
    if not data["tide_points"]:
        raise UpdateFailed(f"No tide data in response for {harbor}")
    return data


def parse_tides(data: str, now: datetime | None = None) -> dict:
    """Parse MET tidal data and return next high/low tides and current height."""
    if now is None:
        now = datetime.now(UTC)
    _LOGGER.debug("Parsing tides, current time: %s", now)

    tide_points = []
    for line in data.splitlines():
        parts = line.split()
        if len(parts) < 8:
            continue

        try:
            # Use TOTAL column (index 7) for tide height
            height = float(parts[7])
            # MET data is in UTC
            tide_dt = datetime(
                int(parts[0]),
                int(parts[1]),
                int(parts[2]),
                int(parts[3]),
                int(parts[4]),
                tzinfo=UTC,
            )
        except ValueError as e:
            # Header lines and out-of-range dates end up here
            _LOGGER.debug("Skipping line due to parse error: %s | %s", line, e)
            continue

        tide_points.append({"datetime": tide_dt, "height": height})

    tide_points.sort(key=lambda x: x["datetime"])

    next_high, next_low = find_next_tides(tide_points, now)
    current_height = interpolate_current_height(tide_points, now)

    return {
        "next_high": next_high or {"datetime": None, "height": None},
        "next_low": next_low or {"datetime": None, "height": None},
        "current_height": current_height,
        "tide_points": tide_points,  # Store for dynamic current_height calculation
    }


def find_next_tides(tide_points: list, now: datetime) -> tuple:
    """Find next high and low tides from tide data points (sorted by datetime)."""
    if len(tide_points) < 5:
        return None, None

    tide_events = []

    # Use a +/-2 sample window for peak/trough detection
    for i in range(2, len(tide_points) - 2):
        curr_point = tide_points[i]
        prev2 = tide_points[i - 2]["height"]
        prev1 = tide_points[i - 1]["height"]
        next1 = tide_points[i + 1]["height"]
        next2 = tide_points[i + 2]["height"]
        curr_height = curr_point["height"]

        is_peak = curr_height >= prev1 and curr_height >= next1 and curr_height > prev2 and curr_height > next2
        is_trough = curr_height <= prev1 and curr_height <= next1 and curr_height < prev2 and curr_height < next2

        # A two-sample plateau matches twice; harmless since only the first
        # future event of each type is used.
        if is_peak:
            tide_events.append({"type": "high", "datetime": curr_point["datetime"], "height": curr_height})
        if is_trough:
            tide_events.append({"type": "low", "datetime": curr_point["datetime"], "height": curr_height})

    future_events = [e for e in tide_events if e["datetime"] > now]
    next_high = next(
        ({"datetime": e["datetime"], "height": e["height"]} for e in future_events if e["type"] == "high"),
        None,
    )
    next_low = next(
        ({"datetime": e["datetime"], "height": e["height"]} for e in future_events if e["type"] == "low"),
        None,
    )

    _LOGGER.debug("Final result - next_high: %s, next_low: %s", next_high, next_low)
    return next_high, next_low


def interpolate_current_height(tide_points: list, now: datetime) -> float | None:
    """Interpolate current water height from tide data points (sorted by datetime)."""
    if not tide_points:
        return None

    before_point = None
    after_point = None
    for point in tide_points:
        if point["datetime"] <= now:
            before_point = point
        else:
            after_point = point
            break

    if not before_point or not after_point:
        # Outside the forecast window: use closest available point
        closest = min(tide_points, key=lambda x: abs((x["datetime"] - now).total_seconds()))
        return closest["height"]

    time_diff = (after_point["datetime"] - before_point["datetime"]).total_seconds()
    time_offset = (now - before_point["datetime"]).total_seconds()
    height_diff = after_point["height"] - before_point["height"]

    return before_point["height"] + (height_diff * time_offset / time_diff)


class METTideSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, harbor, sensor_type):
        super().__init__(coordinator)
        self._harbor = harbor
        self._sensor_type = sensor_type
        self._attr_name = f"Tides {harbor.title()} {sensor_type.replace('_', ' ').title()}"
        self._attr_unique_id = f"met_tides_{harbor.lower()}_{sensor_type}"
        if sensor_type == "current_height":
            self._attr_device_class = SensorDeviceClass.DISTANCE
            self._attr_state_class = SensorStateClass.MEASUREMENT
            self._attr_native_unit_of_measurement = UnitOfLength.METERS
        else:
            self._attr_device_class = SensorDeviceClass.TIMESTAMP

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if self._sensor_type == "current_height":
            self.async_on_remove(
                async_track_time_interval(self.hass, self._async_refresh_height, CURRENT_HEIGHT_REFRESH)
            )

    @callback
    def _async_refresh_height(self, _now: datetime) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self):
        data = self.coordinator.data or {}
        if self._sensor_type == "current_height":
            # Recalculate current height based on current time
            tide_points = data.get("tide_points")
            if not tide_points:
                return None
            height = interpolate_current_height(tide_points, datetime.now(UTC))
            return round(height, 2) if height is not None else None

        tide = data.get(self._sensor_type)
        return tide["datetime"] if tide else None

    @property
    def extra_state_attributes(self):
        attrs = {"harbor": self._harbor.title()}
        if self._sensor_type == "current_height":
            return attrs

        tide = (self.coordinator.data or {}).get(self._sensor_type)
        if not tide or not tide["datetime"]:
            return {}
        return {**attrs, "height_m": tide["height"]}
