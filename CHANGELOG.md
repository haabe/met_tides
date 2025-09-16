# Changelog

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