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

from . import FriscoConfigEntry
from .const import STATUS_LABELS
from .coordinator import FriscoData
from .entity import FriscoEntity


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


def _reservation_window_start(data: FriscoData) -> datetime | None:
    res = data.reservation or {}
    return _dt((res.get("deliveryWindow") or {}).get("startsAt"))


def _reservation_attrs(data: FriscoData) -> dict[str, Any]:
    res = data.reservation or {}
    window = res.get("deliveryWindow") or {}
    extended = res.get("extendedRange") or {}
    return {
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
    }


def _order_window_start(data: FriscoData) -> datetime | None:
    order = data.active_order or {}
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    return _dt(window.get("startsAt"))


def _order_attrs(data: FriscoData) -> dict[str, Any]:
    order = data.active_order
    if not order:
        return {}
    window = (order.get("reservation") or {}).get("deliveryWindow") or {}
    raw_status = order.get("status")
    stats = (order.get("deliveryStatistics") or {}).get("totals") or {}
    return {
        "order_id": order.get("id"),
        "status": STATUS_LABELS.get(raw_status, raw_status),
        "status_raw": raw_status,
        "window_start": window.get("startsAt"),
        "window_end": window.get("endsAt"),
        "placed_at": order.get("placedAt"),
        "payment_method": order.get("paymentMethod"),
        "product_lines": stats.get("lines"),
        "quantity": stats.get("quantity"),
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
        value_fn=lambda data: _dt((data.reservation or {}).get("expiresAt")),
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
