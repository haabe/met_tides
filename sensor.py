import logging
import aiohttp
from datetime import datetime, timezone, timedelta
from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, CoordinatorEntity
from .const import DOMAIN, USER_AGENT

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass, entry, async_add_entities):
    """Set up MET Tides sensors via config entry."""
    harbor = entry.data["harbor"].capitalize()

    # Prefer options over initial data
    sensors = entry.options.get("sensors") or entry.data.get("sensors", ["next_high", "next_low", "current_height"])

    coordinator = DataUpdateCoordinator(
        hass,
        _LOGGER,
        name=f"met_tides_{harbor}",
        update_method=lambda: fetch_tides(harbor),
        update_interval=timedelta(hours=1),
    )

    await coordinator.async_refresh()

    entities = [METTideSensor(coordinator, harbor, s) for s in sensors]
    async_add_entities(entities, True)


async def fetch_tides(harbor: str) -> dict:
    url = f"https://api.met.no/weatherapi/tidalwater/1.1/forecast?harbor={harbor.lower()}"
    headers = {"User-Agent": USER_AGENT}
    try:
        _LOGGER.info("Fetching tide data for %s", harbor)
        async with aiohttp.ClientSession() as session:
            async with session.get(url, headers=headers, timeout=10) as resp:
                text = await resp.text()
                _LOGGER.debug("Raw tide data: %s", text[:1000])  # log first 1000 chars
                _LOGGER.debug("Full raw tide data: %s", text)  # log full response
                return parse_tides(text)
    except Exception as e:
        _LOGGER.error("Error fetching tides: %s", e)
        return {"next_high": "unavailable", "next_low": "unavailable", "current_height": "unavailable"}


def parse_tides(data: str) -> dict:
    """Parse MET tidal data and return next high/low tides and current height."""
    lines = data.splitlines()
    tide_points = []

    now = datetime.now(timezone.utc)
    _LOGGER.debug("Parsing tides, current time: %s", now)
    
    for line in lines:
        parts = line.split()
        if len(parts) < 8:
            continue

        try:
            year = int(parts[0])
            month = int(parts[1])
            day = int(parts[2])
            hour = int(parts[3])
            minute = int(parts[4])
            # Use TOTAL column (index 7) for tide height
            height = float(parts[7])
        except (ValueError, IndexError) as e:
            _LOGGER.debug("Skipping line due to parse error: %s | %s", line, e)
            continue

        # Create datetime in UTC (MET data is in UTC)
        tide_dt = datetime(year, month, day, hour, minute, tzinfo=timezone.utc)
        tide_points.append({"datetime": tide_dt, "height": height})

    # Find high/low tides from the data points
    next_high, next_low = find_next_tides(tide_points, now)
    
    # Calculate current height by interpolation
    current_height = interpolate_current_height(tide_points, now)

    return {
        "next_high": next_high or {"datetime": None, "height": None},
        "next_low": next_low or {"datetime": None, "height": None},
        "current_height": current_height,
        "tide_points": tide_points,  # Store for dynamic current_height calculation
    }

def find_next_tides(tide_points: list, now: datetime) -> tuple:
    """Find next high and low tides from tide data points."""
    if len(tide_points) < 5:
        return None, None
    
    # Sort by datetime to ensure proper order
    tide_points.sort(key=lambda x: x["datetime"])
    
    _LOGGER.debug("Looking for tides after: %s", now)
    _LOGGER.debug("First few tide points: %s", tide_points[:5])
    
    # Find all peaks and troughs in chronological order
    tide_events = []
    
    # Use a wider window for peak/trough detection
    for i in range(2, len(tide_points) - 2):
        curr_point = tide_points[i]
        
        # Get surrounding points for better peak detection
        prev2 = tide_points[i - 2]
        prev1 = tide_points[i - 1]
        next1 = tide_points[i + 1]
        next2 = tide_points[i + 2]
        
        curr_height = curr_point["height"]
        
        # Check for high tide (peak) - more flexible detection
        is_peak = (curr_height >= prev1["height"] and 
                  curr_height >= next1["height"] and 
                  curr_height > prev2["height"] and 
                  curr_height > next2["height"])
        
        # Check for low tide (trough) - more flexible detection
        is_trough = (curr_height <= prev1["height"] and 
                    curr_height <= next1["height"] and 
                    curr_height < prev2["height"] and 
                    curr_height < next2["height"])
        
        if is_peak:
            tide_events.append({"type": "high", "datetime": curr_point["datetime"], "height": curr_height})
            _LOGGER.debug("Found high tide: %s at height %s", curr_point["datetime"], curr_height)
            
        if is_trough:
            tide_events.append({"type": "low", "datetime": curr_point["datetime"], "height": curr_height})
            _LOGGER.debug("Found low tide: %s at height %s", curr_point["datetime"], curr_height)
    
    # Sort tide events by datetime
    tide_events.sort(key=lambda x: x["datetime"])
    
    # Find the immediate next high and low tides after current time
    future_events = [e for e in tide_events if e["datetime"] > now]
    
    next_high = None
    next_low = None
    
    # Find the very next high tide
    for event in future_events:
        if event["type"] == "high":
            next_high = {"datetime": event["datetime"], "height": event["height"]}
            break
    
    # Find the very next low tide
    for event in future_events:
        if event["type"] == "low":
            next_low = {"datetime": event["datetime"], "height": event["height"]}
            break
    
    _LOGGER.debug("Final result - next_high: %s, next_low: %s", next_high, next_low)
    return next_high, next_low


def interpolate_current_height(tide_points: list, now: datetime) -> float:
    """Interpolate current water height from tide data points."""
    if not tide_points:
        return None
    
    # Sort by datetime
    tide_points.sort(key=lambda x: x["datetime"])
    
    # Find surrounding points
    before_point = None
    after_point = None
    
    for point in tide_points:
        if point["datetime"] <= now:
            before_point = point
        elif point["datetime"] > now and after_point is None:
            after_point = point
            break
    
    if not before_point or not after_point:
        # Use closest available point
        closest = min(tide_points, key=lambda x: abs((x["datetime"] - now).total_seconds()))
        return closest["height"]
    
    # Linear interpolation
    time_diff = (after_point["datetime"] - before_point["datetime"]).total_seconds()
    time_offset = (now - before_point["datetime"]).total_seconds()
    height_diff = after_point["height"] - before_point["height"]
    
    return before_point["height"] + (height_diff * time_offset / time_diff)


class METTideSensor(CoordinatorEntity, SensorEntity):
    def __init__(self, coordinator, harbor, sensor_type):
        super().__init__(coordinator)
        self._harbor = harbor
        self._sensor_type = sensor_type

    @property
    def name(self):
        return f"Tides {self._harbor.title()} {self._sensor_type.replace('_', ' ').title()}"

    @property
    def unique_id(self):
        return f"met_tides_{self._harbor.lower()}_{self._sensor_type}"

    @property
    def state(self):
        if self._sensor_type == "current_height":
            # Recalculate current height based on current time
            tide_points = self.coordinator.data.get("tide_points")
            if tide_points:
                now = datetime.now(timezone.utc)
                height = interpolate_current_height(tide_points, now)
                return round(height, 2) if height is not None else None
            return None
        
        tide = self.coordinator.data.get(self._sensor_type)
        return tide["datetime"].isoformat() if tide and tide["datetime"] else None

    @property
    def extra_state_attributes(self):
        if self._sensor_type == "current_height":
            return {"harbor": self._harbor.title(), "unit_of_measurement": "m"}
        
        tide = self.coordinator.data.get(self._sensor_type)
        if not tide or not tide["datetime"]:
            return {}
        return {
            "harbor": self._harbor.title(),
            "height_m": tide["height"]
        }