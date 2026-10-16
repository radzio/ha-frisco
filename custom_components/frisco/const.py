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

# Cancelled orders are gone; everything else may still be on its way.
# NOTE: "Invoiced" is NOT terminal here — Frisco marks an order Invoiced when the
# invoice is generated (at finalisation), and it keeps that status right through
# delivery and after. So whether an order is still "incoming" is decided by its
# delivery window, not by the status string (see the coordinator).
CANCELLED_STATUSES = frozenset(
    {"Cancelled", "CancelledArchived", "Aborted", "AbortedArchived"}
)

# How long after its delivery window ends an order is still shown as "incoming"
# (covers deliveries that run late before the order drops off).
ACTIVE_ORDER_GRACE = timedelta(hours=3)

# Window around the delivery slot in which we attempt live driver tracking and
# poll faster: Frisco creates the live-delivery document around dispatch, which
# can be a while before the slot opens, and the van may still be out after it.
DELIVERY_PRE_WINDOW = timedelta(hours=3)
DELIVERY_POST_WINDOW = timedelta(hours=2)
