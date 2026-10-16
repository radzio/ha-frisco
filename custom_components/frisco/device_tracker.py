"""Driver location while an order is out for delivery."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.device_tracker import SourceType, TrackerEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import FriscoConfigEntry
from .coordinator import (
    FriscoData,
    delivery_coords,
    delivery_eta,
    delivery_last_refreshed,
)
from .entity import FriscoEntity

_LOGGER = logging.getLogger(__name__)

# The confirmed live shape is estimation.coordinates (see coordinator), read via
# delivery_coords(). This depth-first search stays as a resilience fallback: if
# Frisco ever moves the pair, we still find it and log the raw payload once so
# the mapping can be re-confirmed, rather than silently losing the driver.
_COORD_CONTAINERS = ("estimation", "coordinates", "driverCoordinates", "position", "driverPosition", "location")
_LAT_KEYS = ("latitude", "lat")
_LON_KEYS = ("longitude", "lon", "lng")


def _find_coords(obj: Any) -> tuple[float, float] | None:
    """Depth-first search for a lat/lon pair in the delivery payload."""
    if isinstance(obj, dict):
        lat = next((obj[k] for k in _LAT_KEYS if k in obj), None)
        lon = next((obj[k] for k in _LON_KEYS if k in obj), None)
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
        for key in (*_COORD_CONTAINERS, "driver"):
            if key in obj and (found := _find_coords(obj[key])):
                return found
        for value in obj.values():
            if isinstance(value, (dict, list)) and (found := _find_coords(value)):
                return found
    elif isinstance(obj, list):
        for item in obj:
            if found := _find_coords(item):
                return found
    return None


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FriscoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Frisco driver tracker."""
    async_add_entities([FriscoDriverTracker(entry.runtime_data)])


class FriscoDriverTracker(FriscoEntity, TrackerEntity):
    """Where the Frisco van is, while it is delivering the active order."""

    _attr_translation_key = "driver"
    _attr_icon = "mdi:truck-fast"

    def __init__(self, coordinator) -> None:
        super().__init__(coordinator, "driver")
        self._logged_shape = False

    def _coords(self) -> tuple[float, float] | None:
        data: FriscoData = self.coordinator.data
        if not data.delivery:
            return None
        # Known shape first; DFS only if Frisco ever relocates the pair.
        coords = delivery_coords(data.delivery) or _find_coords(data.delivery)
        if coords is None and not self._logged_shape:
            # One-off: capture a real delivery payload to confirm field names.
            _LOGGER.debug("Frisco delivery payload (no coords matched): %s", data.delivery)
            self._logged_shape = True
        return coords

    @property
    def source_type(self) -> SourceType:
        return SourceType.GPS

    @property
    def available(self) -> bool:
        return super().available and self._coords() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        delivery = self.coordinator.data.delivery
        if not delivery:
            return None
        return {
            "estimated_arrival": delivery_eta(delivery),
            "last_refreshed": delivery_last_refreshed(delivery),
        }

    @property
    def latitude(self) -> float | None:
        coords = self._coords()
        return coords[0] if coords else None

    @property
    def longitude(self) -> float | None:
        coords = self._coords()
        return coords[1] if coords else None
