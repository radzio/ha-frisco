<p align="center">
  <img src="images/logo.png" width="96" alt="Frisco">
</p>

<h1 align="center">Frisco for Home Assistant</h1>

<p align="center">
  Reservations, order delivery and driver location from your <a href="https://www.frisco.pl">Frisco.pl</a> account — in Home Assistant.
</p>

<p align="center">
  <a href="https://github.com/hacs/integration"><img src="https://img.shields.io/badge/HACS-Custom-41BDF5.svg" alt="HACS Custom"></a>
  <a href="https://github.com/radzio/ha-frisco/releases"><img src="https://img.shields.io/github/v/release/radzio/ha-frisco?include_prereleases" alt="Release"></a>
  <img src="https://img.shields.io/badge/iot__class-cloud__polling-blue.svg" alt="cloud polling">
</p>

<p align="center">
  🇵🇱 <a href="#-polski">Polski</a> &nbsp;·&nbsp; 🇬🇧 <a href="#-english">English</a>
</p>

---

## 🇵🇱 Polski

Integracja pokazuje w Home Assistant informacje o Twoich zakupach w **Frisco.pl**:

- **Najbliższa rezerwacja** — zarezerwowane okno dostawy oraz **do kiedy jest ważne** (kiedy wygasa zarezerwowany slot, a dla złożonego zamówienia — do kiedy można je edytować).
- **Zamówienie w drodze** — kiedy dotrze zamówienie, które jest w realizacji, wraz z jego statusem (złożone → w realizacji → skompletowane → w dostawie → zrealizowane).
- **Lokalizacja kierowcy** — `device_tracker` pokazujący auto dostawcze na mapie, kiedy zamówienie jest w dostawie.

Integracja działa **tylko do odczytu** — nigdy nie składa ani nie zmienia zamówień.

### Encje

| Encja | Co pokazuje |
|---|---|
| `sensor.frisco_next_reservation` | Początek **najbliższego** zarezerwowanego okna dostawy. Atrybuty: `count` (ile masz rezerwacji), `window_end`, `valid_until`, `modify_until`, `address`, `warehouse`, `is_vip` oraz `all` — lista wszystkich rezerwacji z ich oknami i ważnością. |
| `sensor.frisco_reservation_valid_until` | Do kiedy ważny jest najbliższy zarezerwowany slot. |
| `sensor.frisco_active_order_delivery` | Okno dostawy **najbliższego** zamówienia w drodze. Atrybuty: `count`, `status`, `status_raw`, `window_end`, `order_id`, `placed_at`, `product_lines`, `quantity` oraz `all`. |
| `device_tracker.frisco_driver` | Pozycja GPS kierowcy; dostępna tylko gdy zamówienie jest w dostawie. |

Gdy nic nie jest zarezerwowane / w drodze, odpowiedni sensor ma stan `unknown`, a tracker kierowcy — `unavailable`.

### Instalacja

**HACS (repozytorium własne)**
1. HACS → ⋮ → **Własne repozytoria** → dodaj `https://github.com/radzio/ha-frisco` jako **Integrację**.
2. Zainstaluj **Frisco** i uruchom ponownie Home Assistant.

**Ręcznie** — skopiuj `custom_components/frisco` do katalogu `config/custom_components/` i uruchom ponownie HA.

### Konfiguracja

Ustawienia → Urządzenia i usługi → **Dodaj integrację** → **Frisco**, podaj e-mail i hasło konta Frisco (te same co w aplikacji). Tokeny są odświeżane automatycznie; gdy dane logowania przestaną działać, HA poprosi o ponowne uwierzytelnienie.

### Karta na dashboard

Gotowa karta w stylu **Mushroom** znajduje się w [`examples/dashboard-mushroom.yaml`](examples/dashboard-mushroom.yaml) — pokazuje najbliższą rezerwację, odliczanie ważności, listę rezerwacji (gdy jest ich więcej), zamówienie w drodze i mapę kierowcy.

---

## 🇬🇧 English

This integration surfaces your **Frisco.pl** grocery account in Home Assistant:

- **Next reservation** — the delivery slot you hold and **how long it stays valid** (when the held slot lapses, and until when a placed order can still be edited).
- **Active order delivery** — when the order on its way will arrive, with its status (placed → in implementation → ready → out for delivery → completed).
- **Driver location** — a `device_tracker` showing the van on the map while the order is out for delivery.

It is **read-only** — it never places or changes orders.

### Entities

| Entity | What it shows |
|---|---|
| `sensor.frisco_next_reservation` | Start of your **soonest** held delivery window. Attributes: `count`, `window_end`, `valid_until`, `modify_until`, `address`, `warehouse`, `is_vip`, and `all` — every held reservation with its own window and validity. |
| `sensor.frisco_reservation_valid_until` | When the soonest held slot expires if you don't place the order. |
| `sensor.frisco_active_order_delivery` | Delivery window of the **soonest** order on its way. Attributes: `count`, `status`, `status_raw`, `window_end`, `order_id`, `placed_at`, `product_lines`, `quantity`, and `all`. |
| `device_tracker.frisco_driver` | Driver GPS position; available only while the order is out for delivery. |

When nothing is reserved / in transit, the matching sensor is `unknown` and the driver tracker is `unavailable`.

### Installation

**HACS (custom repository)**
1. HACS → ⋮ → **Custom repositories** → add `https://github.com/radzio/ha-frisco` as an **Integration**.
2. Install **Frisco**, then restart Home Assistant.

**Manual** — copy `custom_components/frisco` into `config/custom_components/` and restart HA.

### Configuration

Settings → Devices & Services → **Add Integration** → **Frisco**, then enter the e-mail and password of your Frisco account (the same ones you use in the app). Tokens refresh automatically; if the credentials ever stop working, Home Assistant prompts for re-authentication.

### Dashboard card

A ready-made **Mushroom** card lives in [`examples/dashboard-mushroom.yaml`](examples/dashboard-mushroom.yaml) — it shows the next reservation, a validity countdown, a list of reservations (when you hold more than one), the active order, and the driver map.

---

### Notes

- Polling is every 5 minutes, dropping to every 60 seconds while an order is out for delivery, so the driver marker stays fresh.
- To see detailed logs:
  ```yaml
  logger:
    logs:
      custom_components.frisco: debug
  ```

### Disclaimer

Unofficial integration. Not affiliated with or endorsed by Frisco.pl. For personal use with your own account. Frisco and the Frisco logo are trademarks of their respective owner.

### License

[MIT](LICENSE)
