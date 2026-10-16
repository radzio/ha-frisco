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
from homeassistant.util import dt as dt_util

from .api import FriscoApiError, FriscoAuthError, FriscoClient
from .const import (
    ACTIVE_ORDER_GRACE,
    CANCELLED_STATUSES,
    DELIVERY_POST_WINDOW,
    DELIVERY_PRE_WINDOW,
    DOMAIN,
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


def _order_window(order: dict[str, Any]) -> tuple[datetime | None, datetime | None]:
    """(start, end) of an order's delivery window."""
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    return _parse_dt(window.get("startsAt")), _parse_dt(window.get("endsAt"))


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
    def _collect_active_orders(
        orders: list[dict[str, Any]], now: datetime
    ) -> list[dict[str, Any]]:
        """Orders still on their way, soonest window first.

        An order counts as incoming while it isn't cancelled and its delivery
        window hasn't finished (plus a grace period for late deliveries). The
        status string is deliberately ignored — Frisco leaves it "Invoiced"
        throughout delivery, so filtering on it would hide the order entirely.
        """
        active: list[dict[str, Any]] = []
        for order in orders:
            if order.get("status") in CANCELLED_STATUSES:
                continue
            _, end = _order_window(order)
            if end is not None and end >= now - ACTIVE_ORDER_GRACE:
                active.append(order)
        active.sort(key=_by_start(lambda o: _order_window(o)[0]))
        return active

    @staticmethod
    def _en_route_order(
        active_orders: list[dict[str, Any]], now: datetime
    ) -> dict[str, Any] | None:
        """Soonest order whose delivery slot is current (drives live tracking)."""
        for order in active_orders:
            start, end = _order_window(order)
            if (
                start is not None
                and end is not None
                and start - DELIVERY_PRE_WINDOW <= now <= end + DELIVERY_POST_WINDOW
            ):
                return order
        return None

    async def _async_update_data(self) -> FriscoData:
        try:
            cart = await self.client.async_get_cart()
            orders = await self.client.async_get_orders()
        except FriscoAuthError as err:
            # Surfaces a re-auth flow in the UI rather than just failing forever.
            raise ConfigEntryAuthFailed(str(err)) from err
        except FriscoApiError as err:
            raise UpdateFailed(str(err)) from err

        now = dt_util.now()
        reservations = self._collect_reservations(cart)
        active_orders = self._collect_active_orders(orders, now)
        en_route = self._en_route_order(active_orders, now)

        delivery: dict[str, Any] | None = None
        if en_route is not None:
            try:
                # 404 (document not created yet) comes back as None — expected
                # until Frisco actually dispatches the van.
                delivery = await self.client.async_get_order_delivery(en_route["id"])
            except FriscoApiError as err:
                _LOGGER.debug("delivery detail fetch failed: %s", err)

        # Poll faster while an order is in its delivery window.
        self.update_interval = (
            UPDATE_INTERVAL_DELIVERY if en_route is not None else UPDATE_INTERVAL
        )

        return FriscoData(
            reservations=reservations,
            active_orders=active_orders,
            delivery=delivery,
        )
