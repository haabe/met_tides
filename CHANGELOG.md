# Changelog

## [Unreleased]

### Fixed
- Failed API requests no longer crash the sensors (`'str' object is not subscriptable`); entities now go unavailable and recover on the next successful fetch
- HTTP error responses are no longer parsed as tide data
- `current_height` now actually updates every 5 minutes between hourly fetches
- Setup is retried by Home Assistant when MET is unreachable at startup
- The same harbor can no longer be added twice
- The config flow no longer offers an empty harbor when the harbor list can't be fetched; it falls back to the harbors listed in the API documentation
- Use the documented API endpoints (`/1.1/?harbor=` and `/1.1/available`) instead of `/forecast` and `/available.xml`

### Changed
- Identify with a proper User-Agent, as required by MET Norway's terms of service
- Use Home Assistant's shared HTTP session
- Timestamp sensors use the `timestamp` device class; `current_height` has a proper `m` unit and state class for long-term statistics

### Added
- Test suite (pytest + pytest-homeassistant-custom-component), CI (lint, tests, hassfest, HACS validation), release workflow and Dependabot

## [1.1.2] - 2025-01-16

### Fixed
- Fixed next tide detection to find immediate next high/low tides instead of any future ones
- Ensures proper tide timing when multiple tides exist before the previously detected ones

## [1.1.1] - 2025-01-16

### Fixed
- Fixed next_high/next_low tide timing sequence to respect chronological order
- Resolved issue where next_high showed ~24h and next_low showed current time
- Improved tide detection to properly follow 6-hour tide cycle timing

## [1.1.0] - 2025-09-16

### Added
- Real-time current height updates based on current time
- Dynamic interpolation for current_height sensor between data fetches
- INFO level logging when fetching new tide data

### Changed
- Current height now updates continuously instead of only when data is fetched
- Improved timezone handling with proper UTC support
- Enhanced tide detection algorithm with wider peak/trough detection window

## [1.0.1] - 2025-09-16

### Fixed
- Fixed tide parsing to properly detect high/low tides from height data
- Fixed async_forward_entry_unload parameter type error
- Improved error handling and debug logging

## [1.0.0] - 2025-09-16

### Added
- Initial release
- Next high tide sensor with datetime and height
- Next low tide sensor with datetime and height  
- Current water height sensor with real-time interpolation
- Support for all Norwegian harbors in MET TidalWater API
- Automatic tide detection from height data (peaks/troughs)
- Hourly data updates from MET Norway
- Home Assistant config flow integration

### Technical
- Uses MET Norway TidalWater API v1.1
- Linear interpolation for current height calculation
- Proper error handling and logging
- DataUpdateCoordinator for efficient updates