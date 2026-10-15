"""Data coordinator: one poll feeds every Frisco entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import logging
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import FriscoApiError, FriscoAuthError, FriscoClient
from .const import (
    DOMAIN,
    INACTIVE_STATUSES,
    OUT_FOR_DELIVERY_STATUSES,
    UPDATE_INTERVAL,
    UPDATE_INTERVAL_DELIVERY,
)

_LOGGER = logging.getLogger(__name__)


@dataclass
class FriscoData:
    """Everything the entities read, assembled once per poll."""

    reservation: dict[str, Any] | None = None
    active_order: dict[str, Any] | None = None
    delivery: dict[str, Any] | None = None


def _window_start(obj: dict[str, Any]) -> datetime | None:
    """Parse reservation.deliveryWindow.startsAt into an aware datetime."""
    window = (obj.get("reservation") or {}).get("deliveryWindow") or {}
    raw = window.get("startsAt")
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


class FriscoCoordinator(DataUpdateCoordinator[FriscoData]):
    """Polls Frisco and exposes a single consolidated snapshot."""

    def __init__(
        self, hass: HomeAssistant, entry: ConfigEntry, client: FriscoClient
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=UPDATE_INTERVAL,
            config_entry=entry,
        )
        self.client = client

    def _select_active_order(
        self, orders: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        """The soonest-arriving order that is still on its way.

        Frisco returns orders newest-first. We keep those whose status is not
        terminal, then prefer the one with the earliest delivery window — that is
        the next one to actually show up at the door.
        """
        active = [o for o in orders if o.get("status") not in INACTIVE_STATUSES]
        if not active:
            return None
        dateless = datetime.max.replace(tzinfo=None)
        return min(
            active,
            key=lambda o: (_window_start(o) or dateless).replace(tzinfo=None),
        )

    async def _async_update_data(self) -> FriscoData:
        try:
            cart = await self.client.async_get_cart()
            orders = await self.client.async_get_orders()
        except FriscoAuthError as err:
            # Surfaces a re-auth flow in the UI rather than just failing forever.
            raise ConfigEntryAuthFailed(str(err)) from err
        except FriscoApiError as err:
            raise UpdateFailed(str(err)) from err

        active_order = self._select_active_order(orders)

        delivery: dict[str, Any] | None = None
        out_for_delivery = (
            active_order is not None
            and active_order.get("status") in OUT_FOR_DELIVERY_STATUSES
        )
        if out_for_delivery:
            try:
                delivery = await self.client.async_get_order_delivery(
                    active_order["id"]
                )
            except FriscoApiError as err:
                # Don't fail the whole poll just because live tracking hiccups.
                _LOGGER.debug("delivery detail fetch failed: %s", err)

        # Poll faster while a driver is en route, slower the rest of the time.
        self.update_interval = (
            UPDATE_INTERVAL_DELIVERY if out_for_delivery else UPDATE_INTERVAL
        )

        return FriscoData(
            reservation=cart.get("reservation"),
            active_order=active_order,
            delivery=delivery,
        )
