"""Data coordinator: one poll feeds every Frisco entity."""

from __future__ import annotations

from dataclasses import dataclass, field
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

# Sorts undated items last rather than crashing on the comparison.
_LATEST = datetime.max.replace(tzinfo=None)


@dataclass
class FriscoData:
    """Everything the entities read, assembled once per poll.

    Both lists are sorted by delivery-window start (soonest first), so entities
    can take ``[0]`` as the primary item and expose the rest as attributes.
    """

    reservations: list[dict[str, Any]] = field(default_factory=list)
    active_orders: list[dict[str, Any]] = field(default_factory=list)
    delivery: dict[str, Any] | None = None


def _parse_dt(raw: str | None) -> datetime | None:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _reservation_start(reservation: dict[str, Any]) -> datetime | None:
    """Delivery-window start of a bare reservation object."""
    return _parse_dt((reservation.get("deliveryWindow") or {}).get("startsAt"))


def _order_start(order: dict[str, Any]) -> datetime | None:
    """Delivery-window start of an order (window lives under order.reservation)."""
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    return _parse_dt(window.get("startsAt"))


def _by_start(start_of):
    """Sort key: soonest window first, naive for safe comparison across tz."""
    return lambda item: (start_of(item) or _LATEST).replace(tzinfo=None)


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

    @staticmethod
    def _collect_reservations(cart: dict[str, Any]) -> list[dict[str, Any]]:
        """All held reservations: the primary `reservation` plus `savedReservations`."""
        reservations: list[dict[str, Any]] = []
        if primary := cart.get("reservation"):
            reservations.append(primary)
        reservations.extend(cart.get("savedReservations") or [])
        reservations.sort(key=_by_start(_reservation_start))
        return reservations

    @staticmethod
    def _collect_active_orders(orders: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Every order still on its way, soonest delivery first."""
        active = [o for o in orders if o.get("status") not in INACTIVE_STATUSES]
        active.sort(key=_by_start(_order_start))
        return active

    async def _async_update_data(self) -> FriscoData:
        try:
            cart = await self.client.async_get_cart()
            orders = await self.client.async_get_orders()
        except FriscoAuthError as err:
            # Surfaces a re-auth flow in the UI rather than just failing forever.
            raise ConfigEntryAuthFailed(str(err)) from err
        except FriscoApiError as err:
            raise UpdateFailed(str(err)) from err

        reservations = self._collect_reservations(cart)
        active_orders = self._collect_active_orders(orders)

        # The order whose driver (if any) we track: soonest one that's en route.
        en_route = next(
            (o for o in active_orders if o.get("status") in OUT_FOR_DELIVERY_STATUSES),
            None,
        )
        delivery: dict[str, Any] | None = None
        if en_route is not None:
            try:
                delivery = await self.client.async_get_order_delivery(en_route["id"])
            except FriscoApiError as err:
                # Don't fail the whole poll just because live tracking hiccups.
                _LOGGER.debug("delivery detail fetch failed: %s", err)

        # Poll faster while a driver is en route, slower the rest of the time.
        self.update_interval = (
            UPDATE_INTERVAL_DELIVERY if en_route is not None else UPDATE_INTERVAL
        )

        return FriscoData(
            reservations=reservations,
            active_orders=active_orders,
            delivery=delivery,
        )
