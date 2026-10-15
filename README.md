# Frisco for Home Assistant

A custom integration that surfaces your [Frisco.pl](https://www.frisco.pl) grocery
account in Home Assistant:

- **Next reservation** — the delivery slot you currently hold, and **how long it
  stays valid** (when the held slot lapses, and until when a placed order can still
  be edited).
- **Active order delivery** — when the order that is on its way will arrive, with
  its status (placed → in implementation → ready → out for delivery → completed).
- **Driver location** — a `device_tracker` showing the van on the map while the
  order is out for delivery.

It talks to the same private API the official Frisco mobile app uses (OAuth2
password grant against `commerce.frisco.pl`). It is read-only — it never places
or changes orders.

## Entities

| Entity | What it shows |
|---|---|
| `sensor.frisco_next_reservation` | Start of your **soonest** held delivery window (timestamp). Attributes: `count` (how many reservations you hold), `window_end`, `valid_until`, `modify_until`, `address`, `warehouse`, `is_vip`, and `all` — a list of every held reservation with its own window and validity. |
| `sensor.frisco_reservation_valid_until` | When the soonest held slot expires if you don't place the order. |
| `sensor.frisco_active_order_delivery` | Delivery window start of the **soonest** order on its way. Attributes: `count` (orders in flight), `status`, `status_raw`, `window_end`, `order_id`, `placed_at`, `product_lines`, `quantity`, and `all` — every active order with its status and window. |
| `device_tracker.frisco_driver` | Driver GPS position; `available` only while the order status is *out for delivery*. |

When nothing is reserved / in transit, the corresponding sensor is `unknown` and
the driver tracker is `unavailable`.

## Installation

### HACS (custom repository)
1. HACS → ⋮ → **Custom repositories** → add this repo as an **Integration**.
2. Install **Frisco**, then restart Home Assistant.

### Manual
Copy `custom_components/frisco` into your Home Assistant `config/custom_components/`
directory and restart.

## Configuration

Settings → Devices & Services → **Add Integration** → **Frisco**, then enter the
e-mail and password of your Frisco account (the same ones you use in the app).
The password is stored in the config entry; your tokens are refreshed
automatically. If Frisco ever rejects the stored credentials, Home Assistant
raises a re-authentication prompt.

## Notes

- Polling is every 5 minutes, dropping to every 60 seconds while an order is out
  for delivery so the driver marker stays fresh.
- The live-delivery payload (and therefore the exact driver-coordinate fields)
  can only be observed while a van is actually en route; the tracker searches the
  payload for a latitude/longitude pair and logs the raw shape at debug level the
  first time it can't find one, so the mapping can be confirmed against a real
  delivery. Enable with:
  ```yaml
  logger:
    logs:
      custom_components.frisco: debug
  ```

## Disclaimer

Unofficial. Not affiliated with or endorsed by Frisco.pl. Uses a private API that
may change without notice. For personal use with your own account.
