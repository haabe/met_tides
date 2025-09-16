# MET Tides

A Home Assistant custom component that provides tidal information for Norwegian harbors using the [MET Norway TidalWater API](https://api.met.no/weatherapi/tidalwater/1.1/documentation).

## Features

- **Next High Tide**: Shows the date/time and height of the next high tide
- **Next Low Tide**: Shows the date/time and height of the next low tide  
- **Current Water Height**: Real-time water level interpolated from tidal forecast data
- Updates every hour with fresh data from MET Norway
- Supports all harbors available in the MET TidalWater API

## Installation

### HACS (Recommended)

1. Open HACS in Home Assistant
2. Go to "Integrations"
3. Click the three dots menu and select "Custom repositories"
4. Add this repository URL and select "Integration" as category
5. Click "Add"
6. Find "MET Tides" in the integration list and install it
7. Restart Home Assistant

### Manual Installation

1. Download the `met_tides` folder from this repository
2. Copy it to your `custom_components` directory in your Home Assistant config folder
3. Restart Home Assistant

## Configuration

1. Go to Settings → Devices & Services
2. Click "Add Integration" and search for "MET Tides"
3. Enter a Norwegian harbor name (e.g., "trondheim", "bergen", "oslo")
4. Select which sensors you want to create
5. Click "Submit"

## Sensors Created

The integration creates three sensors for each configured harbor:

- `sensor.tides_[harbor]_next_high` - Next high tide datetime with height in attributes
- `sensor.tides_[harbor]_next_low` - Next low tide datetime with height in attributes
- `sensor.tides_[harbor]_current_height` - Current water height in meters

## Supported Harbors

Any harbor supported by the MET Norway TidalWater API. Common examples:
- trondheim
- bergen
- oslo
- stavanger
- kristiansand
- tromsø

## Data Source

This integration uses the [MET Norway TidalWater API](https://api.met.no/weatherapi/tidalwater/1.1/documentation) which provides tidal forecasts for Norwegian coastal locations.
