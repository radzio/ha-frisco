"""Frisco sensors: next reservation, its validity, and the active order."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util import dt as dt_util

from . import FriscoConfigEntry
from .const import STATUS_LABELS
from .coordinator import FriscoData, delivery_eta, delivery_last_refreshed
from .entity import FriscoEntity


def _order_status(order: dict[str, Any], en_route_id: str | None = None) -> str:
    """Human delivery status.

    Prefers the *real* dispatch signal: when Frisco has created the order's
    delivery document (``en_route_id``), the van is genuinely out — no guessing.
    Only the softer pre-dispatch states fall back to the window, because the API
    exposes nothing else there (``status`` stays "Invoiced" throughout).
    """
    if en_route_id and order.get("id") == en_route_id:
        return "Out for delivery"
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    start = _dt(window.get("startsAt"))
    end = _dt(window.get("endsAt"))
    now = dt_util.now()
    if end and now > end:
        return "Delivered"
    if start and end and start <= now <= end:
        return "In delivery window"
    if order.get("status") in ("Invoiced", "Archived"):
        return "Confirmed"
    return STATUS_LABELS.get(order.get("status"), order.get("status"))


def _dt(raw: str | None) -> datetime | None:
    """ISO-8601 string (with offset) -> aware datetime, or None."""
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _format_address(addr: dict[str, Any] | None) -> str | None:
    """shippingAddress dict -> 'ul. Lema 19/136, 31-571 Kraków'."""
    if not addr:
        return None
    line = addr.get("street", "")
    if building := addr.get("buildingNumber"):
        line = f"{line} {building}".strip()
    if apartment := addr.get("apartmentNumber"):
        line = f"{line}/{apartment}"
    city = " ".join(p for p in (addr.get("postcode"), addr.get("city")) if p)
    return ", ".join(p for p in (line.strip(), city) if p) or None


@dataclass(frozen=True, kw_only=True)
class FriscoSensorDescription(SensorEntityDescription):
    """Describes a Frisco sensor via pure functions over the snapshot."""

    value_fn: Callable[[FriscoData], datetime | str | None]
    attrs_fn: Callable[[FriscoData], dict[str, Any]] | None = None


def _reservation_summary(res: dict[str, Any]) -> dict[str, Any]:
    """Compact per-reservation record for the `all` attribute list."""
    window = res.get("deliveryWindow") or {}
    return {
        "window_start": window.get("startsAt"),
        "window_end": window.get("endsAt"),
        "valid_until": res.get("expiresAt"),
        "modify_until": window.get("finalAt") or window.get("closesAt"),
        "address": _format_address(res.get("shippingAddress")),
    }


def _reservation_window_start(data: FriscoData) -> datetime | None:
    if not data.reservations:
        return None
    return _dt((data.reservations[0].get("deliveryWindow") or {}).get("startsAt"))


def _reservation_attrs(data: FriscoData) -> dict[str, Any]:
    reservations = data.reservations
    if not reservations:
        return {"count": 0}
    # Soonest reservation drives the detailed fields; the rest are in `all`.
    res = reservations[0]
    window = res.get("deliveryWindow") or {}
    extended = res.get("extendedRange") or {}
    return {
        "count": len(reservations),
        "window_start": window.get("startsAt"),
        "window_end": window.get("endsAt"),
        "extended_window_start": extended.get("startsAt"),
        "extended_window_end": extended.get("endsAt"),
        "valid_until": res.get("expiresAt"),
        "modify_until": window.get("finalAt") or window.get("closesAt"),
        "warehouse": window.get("warehouse"),
        "delivery_method": window.get("deliveryMethod"),
        "is_vip": res.get("isVipReservation"),
        "address": _format_address(res.get("shippingAddress")),
        "all": [_reservation_summary(r) for r in reservations],
    }


def _valid_until(data: FriscoData) -> datetime | None:
    if not data.reservations:
        return None
    return _dt(data.reservations[0].get("expiresAt"))


def _order_summary(order: dict[str, Any], en_route_id: str | None = None) -> dict[str, Any]:
    """Compact per-order record for the `all` attribute list."""
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    return {
        "order_id": order.get("id"),
        "status": _order_status(order, en_route_id),
        "status_raw": order.get("status"),
        "window_start": window.get("startsAt"),
        "window_end": window.get("endsAt"),
    }


def _order_window_start(data: FriscoData) -> datetime | None:
    if not data.active_orders:
        return None
    window = (data.active_orders[0].get("reservation") or {}).get("deliveryWindow") or {}
    return _dt(window.get("startsAt"))


def _order_attrs(data: FriscoData) -> dict[str, Any]:
    orders = data.active_orders
    if not orders:
        return {"count": 0}
    order = orders[0]
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    stats = (order.get("deliveryStatistics") or {}).get("totals") or {}
    en_route = data.en_route_order_id
    dispatched = en_route is not None and order.get("id") == en_route
    return {
        "count": len(orders),
        "order_id": order.get("id"),
        "status": _order_status(order, en_route),
        "status_raw": order.get("status"),
        # True once Frisco has actually dispatched this order (real signal).
        "dispatched": dispatched,
        # Precise arrival once dispatched; None beforehand (window is the guide).
        "estimated_arrival": delivery_eta(data.delivery) if dispatched else None,
        "driver_last_seen": delivery_last_refreshed(data.delivery) if dispatched else None,
        "window_start": window.get("startsAt"),
        "window_end": window.get("endsAt"),
        "placed_at": order.get("placedAt"),
        "payment_method": order.get("paymentMethod"),
        "product_lines": stats.get("lines"),
        "quantity": stats.get("quantity"),
        "all": [_order_summary(o, data.en_route_order_id) for o in orders],
    }


SENSORS: tuple[FriscoSensorDescription, ...] = (
    FriscoSensorDescription(
        key="next_reservation",
        translation_key="next_reservation",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:calendar-clock",
        value_fn=_reservation_window_start,
        attrs_fn=_reservation_attrs,
    ),
    FriscoSensorDescription(
        key="reservation_valid_until",
        translation_key="reservation_valid_until",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:timer-sand",
        value_fn=_valid_until,
    ),
    FriscoSensorDescription(
        key="active_order_delivery",
        translation_key="active_order_delivery",
        device_class=SensorDeviceClass.TIMESTAMP,
        icon="mdi:truck-delivery",
        value_fn=_order_window_start,
        attrs_fn=_order_attrs,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: FriscoConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Frisco sensors."""
    coordinator = entry.runtime_data
    async_add_entities(FriscoSensor(coordinator, desc) for desc in SENSORS)


class FriscoSensor(FriscoEntity, SensorEntity):
    """A Frisco sensor driven by its description's functions."""

    entity_description: FriscoSensorDescription

    def __init__(self, coordinator, description: FriscoSensorDescription) -> None:
        super().__init__(coordinator, description.key)
        self.entity_description = description

    @property
    def native_value(self) -> datetime | str | None:
        return self.entity_description.value_fn(self.coordinator.data)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        if self.entity_description.attrs_fn is None:
            return None
        return self.entity_description.attrs_fn(self.coordinator.data)
