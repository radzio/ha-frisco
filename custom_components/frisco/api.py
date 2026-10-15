"""Thin async client for the Frisco commerce API.

Only the read endpoints the integration needs are implemented. Auth mirrors the
mobile app exactly: an OAuth2 *password* grant against /connect/token, with the
returned refresh_token used to mint new access tokens until it, too, lapses —
at which point we fall back to a full password login.
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from aiohttp import ClientResponseError, ClientSession

from .const import BASE_URL, DEFAULT_HEADERS, TOKEN_ENDPOINT

_LOGGER = logging.getLogger(__name__)

# Refresh the access token this many seconds before it actually expires, so a
# request never races the expiry. The app's tokens live ~600s.
_TOKEN_SKEW = 30


class FriscoAuthError(Exception):
    """Credentials were rejected (bad username/password, or refresh lapsed)."""


class FriscoApiError(Exception):
    """A data request failed for a non-auth reason."""


class FriscoClient:
    """Authenticated access to a single Frisco account."""

    def __init__(
        self,
        session: ClientSession,
        username: str,
        password: str,
        *,
        visitor_id: str | None = None,
        user_id: str | None = None,
    ) -> None:
        self._session = session
        self._username = username
        self._password = password
        # The visitor id is a stable per-install UUID; persist it across restarts
        # so Frisco sees one device rather than a new one every reload.
        self._visitor_id = visitor_id or str(uuid.uuid4())
        self._user_id = user_id
        self._access_token: str | None = None
        self._refresh_token: str | None = None
        self._expires_at: float = 0.0

    @property
    def visitor_id(self) -> str:
        return self._visitor_id

    @property
    def user_id(self) -> str | None:
        return self._user_id

    # -- auth -----------------------------------------------------------------

    def _base_headers(self) -> dict[str, str]:
        return {**DEFAULT_HEADERS, "X-Frisco-VisitorId": self._visitor_id}

    async def _token_request(self, form: dict[str, str]) -> None:
        """POST to /connect/token and absorb the token response."""
        headers = {
            **self._base_headers(),
            "Content-Type": "application/x-www-form-urlencoded",
        }
        async with self._session.post(
            f"{BASE_URL}{TOKEN_ENDPOINT}", data=form, headers=headers
        ) as resp:
            body = await resp.json(content_type=None)
            if resp.status != 200:
                # OpenIddict returns {error, error_description}; invalid_grant =
                # wrong credentials, which the user must fix, so flag it distinctly.
                err = (body or {}).get("error") if isinstance(body, dict) else None
                desc = (body or {}).get("error_description") if isinstance(body, dict) else body
                if err in ("invalid_grant", "invalid_request", "invalid_client"):
                    raise FriscoAuthError(desc or err)
                raise FriscoApiError(f"token request failed ({resp.status}): {desc}")

        self._access_token = body["access_token"]
        self._refresh_token = body.get("refresh_token", self._refresh_token)
        self._expires_at = time.monotonic() + int(body.get("expires_in", 600))
        # The token response echoes the resolved ids; trust them over anything cached.
        self._user_id = str(body.get("user_id") or self._user_id or "")
        if body.get("visitor_id"):
            self._visitor_id = body["visitor_id"]

    async def async_login(self) -> None:
        """Full password-grant login. Validates credentials; sets ids/tokens."""
        await self._token_request(
            {
                "grant_type": "password",
                "username": self._username,
                "password": self._password,
            }
        )

    async def _async_refresh(self) -> None:
        """Mint a new access token from the refresh token, or re-login."""
        if not self._refresh_token:
            await self.async_login()
            return
        try:
            await self._token_request(
                {"grant_type": "refresh_token", "refresh_token": self._refresh_token}
            )
        except FriscoAuthError:
            # Refresh token lapsed/rotated out — fall back to password.
            _LOGGER.debug("Frisco refresh token rejected, re-logging in")
            await self.async_login()

    async def _async_ensure_token(self) -> None:
        if self._access_token is None:
            await self.async_login()
        elif time.monotonic() >= self._expires_at - _TOKEN_SKEW:
            await self._async_refresh()

    # -- requests -------------------------------------------------------------

    async def _get(self, path: str) -> Any:
        await self._async_ensure_token()
        headers = {
            **self._base_headers(),
            "Authorization": f"Bearer {self._access_token}",
        }
        url = f"{BASE_URL}{path}"
        async with self._session.get(url, headers=headers) as resp:
            if resp.status == 401:
                # Token went stale early; refresh once and retry.
                await self._async_refresh()
                headers["Authorization"] = f"Bearer {self._access_token}"
                async with self._session.get(url, headers=headers) as retry:
                    return await self._read(retry, path)
            return await self._read(resp, path)

    @staticmethod
    async def _read(resp: Any, path: str) -> Any:
        if resp.status == 404:
            # Expected when a sub-resource (e.g. live delivery) doesn't exist yet.
            return None
        try:
            resp.raise_for_status()
        except ClientResponseError as err:
            raise FriscoApiError(f"GET {path} -> {resp.status}") from err
        return await resp.json(content_type=None)

    # -- endpoints ------------------------------------------------------------

    async def async_get_cart(self) -> dict[str, Any]:
        """Cart, which carries the current held `reservation`."""
        return await self._get(f"/api/v1/users/{self._user_id}/cart") or {}

    async def async_get_orders(self, page_size: int = 10) -> list[dict[str, Any]]:
        """Most recent orders (newest first)."""
        data = await self._get(
            f"/api/v1/users/{self._user_id}/orders?pageSize={page_size}"
        )
        return (data or {}).get("items", [])

    async def async_get_order_delivery(self, order_id: str) -> dict[str, Any] | None:
        """Live delivery detail for one order (driver coordinates); None if idle.

        order_id is the full id as returned by the orders list, e.g. "739740/260044".
        """
        return await self._get(f"/api/v1/users/{self._user_id}/orders/{order_id}/delivery")
