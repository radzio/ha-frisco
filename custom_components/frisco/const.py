"""Constants for the Frisco integration."""

from __future__ import annotations

from datetime import timedelta

DOMAIN = "frisco"

# --- API ---------------------------------------------------------------------
# Base host used by the official Frisco mobile app (Expo/React Native, v6.6.0).
# The OAuth token endpoint lives at the host root (/connect/token); every data
# call is under /api/v1 or /api/v2 and is scoped to the logged-in user id.
BASE_URL = "https://commerce.frisco.pl"
TOKEN_ENDPOINT = "/connect/token"

# Headers the app sends on every request. Without X-Frisco-Client the API can
# answer differently; X-Frisco-ApiVersion=2 is what the current app uses.
APP_VERSION = "6.6.0"
DEFAULT_HEADERS = {
    "Accept": "application/json",
    "X-Frisco-ApiVersion": "2",
    "X-Frisco-Client": "mobile-app",
    "X-Frisco-Features": "BalanceAmount=1,DynamicStock=1",
    "User-Agent": f"FriscoMobile/{APP_VERSION} (android; 14)",
}

# --- Config entry keys -------------------------------------------------------
CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_USER_ID = "user_id"
CONF_VISITOR_ID = "visitor_id"

# --- Polling -----------------------------------------------------------------
# Normal cadence; the API data (reservations, order windows) changes slowly.
UPDATE_INTERVAL = timedelta(minutes=5)
# Faster cadence while an order is actively out for delivery, so the driver
# location on the map stays fresh without hammering the API the rest of the time.
UPDATE_INTERVAL_DELIVERY = timedelta(seconds=60)

# --- Order status model (decoded from the app's i18n maps) -------------------
# Raw status -> human label. Kept here so labels and the active/delivery sets
# below are defined in one place and easy to adjust if Frisco adds a status.
STATUS_LABELS: dict[str, str] = {
    "Placed": "Placed",
    "Transferred": "In implementation",
    "Paid": "Paid",
    "Ready": "Ready",
    "Sent": "Sent",
    "Delivery": "Out for delivery",
    "Invoiced": "Completed",
    "Archived": "Completed",
    "Cancelled": "Cancelled",
    "CancelledArchived": "Cancelled",
    "Aborted": "Cancelled",
    "AbortedArchived": "Cancelled",
}

# Terminal statuses: the order is done or gone and is never "active".
COMPLETED_STATUSES = frozenset({"Invoiced", "Archived"})
CANCELLED_STATUSES = frozenset(
    {"Cancelled", "CancelledArchived", "Aborted", "AbortedArchived"}
)
# An order is "active" (still coming) when it is neither completed nor cancelled.
INACTIVE_STATUSES = COMPLETED_STATUSES | CANCELLED_STATUSES

# Statuses in which a driver is on the road and /orders/{id}/delivery exists.
# "Sent" is included defensively: the app treats both as dispatched. If only
# "Delivery" ever carries coordinates this set is harmless.
OUT_FOR_DELIVERY_STATUSES = frozenset({"Delivery", "Sent"})
