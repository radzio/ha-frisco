"""Shared base for Frisco entities."""

from __future__ import annotations

from homeassistant.helpers.device_info import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import FriscoCoordinator


class FriscoEntity(CoordinatorEntity[FriscoCoordinator]):
    """Base entity: shared device, coordinator wiring, stable unique_id."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: FriscoCoordinator, key: str) -> None:
        super().__init__(coordinator)
        user_id = coordinator.client.user_id
        self._attr_unique_id = f"{user_id}_{key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, str(user_id))},
            name="Frisco",
            manufacturer="Frisco.pl",
        )
