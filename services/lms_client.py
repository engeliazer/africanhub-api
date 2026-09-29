"""
LMS (Library Management System) client for book catalog and access tokens.

Implements the integration described in books.md: system OAuth, catalog sync,
grant/revoke/status for content tokens used by the reader client.
"""

import logging
import os
import threading
import time
from typing import Any, Dict, List, Optional

import requests

from services.vdocipher_service import retry_on_failure

logger = logging.getLogger(__name__)


class LMSClientError(Exception):
    """Raised when the LMS API returns an error response."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: Any = None):
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class LMSClient:
    """HTTP client for the external LMS API."""

    def __init__(self):
        self.base_url = os.getenv("LMS_BASE_URL", "").rstrip("/")
        self.client_id = os.getenv("LMS_CLIENT_ID")
        self.client_secret = os.getenv("LMS_CLIENT_SECRET")

        self._system_token: Optional[str] = None
        self._system_token_expires_at: float = 0
        self._token_lock = threading.Lock()

        if not self.base_url:
            raise ValueError("LMS_BASE_URL not set in environment variables")
        if not self.client_id or not self.client_secret:
            raise ValueError("LMS_CLIENT_ID and LMS_CLIENT_SECRET must be set in environment variables")

    @property
    def is_configured(self) -> bool:
        return bool(self.base_url and self.client_id and self.client_secret)

    def absolute_url(self, path: str) -> str:
        """Convert an LMS-relative path to a full URL for the reader client."""
        if not path:
            return self.base_url
        if path.startswith("http://") or path.startswith("https://"):
            return path
        if not path.startswith("/"):
            path = f"/{path}"
        return f"{self.base_url}{path}"

    def _normalize_reader_urls(self, reader: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if not reader:
            return reader
        normalized = dict(reader)
        for key in ("cover_url", "first_page_url", "search_url"):
            if key in normalized and normalized[key]:
                normalized[key] = self.absolute_url(normalized[key])
        return normalized

    def _request(
        self,
        method: str,
        path: str,
        *,
        params: Optional[Dict[str, Any]] = None,
        json: Optional[Dict[str, Any]] = None,
        use_system_auth: bool = True,
        timeout: int = 30,
    ) -> Any:
        url = f"{self.base_url}{path}" if path.startswith("/") else f"{self.base_url}/{path}"
        headers = {"Content-Type": "application/json"}
        if use_system_auth:
            headers["Authorization"] = f"Bearer {self.get_system_token()}"

        try:
            response = requests.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json,
                timeout=timeout,
            )
        except requests.exceptions.Timeout as exc:
            raise LMSClientError("LMS API timeout", status_code=504) from exc
        except requests.exceptions.RequestException as exc:
            raise LMSClientError(f"LMS API request failed: {exc}") from exc

        if response.status_code >= 400:
            body: Any
            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise LMSClientError(
                f"LMS API error ({response.status_code})",
                status_code=response.status_code,
                response_body=body,
            )

        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return response.text

    @retry_on_failure(max_retries=2, delay=1)
    def authenticate(self) -> str:
        """Obtain a short-lived system JWT via client_credentials grant."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        data = self._request("POST", "/oauth/token", json=payload, use_system_auth=False)

        access_token = data.get("access_token") if isinstance(data, dict) else None
        if not access_token:
            raise LMSClientError("LMS OAuth response missing access_token", response_body=data)

        expires_in = 900
        if isinstance(data, dict):
            expires_in = int(data.get("expires_in") or expires_in)

        with self._token_lock:
            self._system_token = access_token
            # Refresh one minute before expiry.
            self._system_token_expires_at = time.time() + max(expires_in - 60, 60)

        return access_token

    def get_system_token(self) -> str:
        with self._token_lock:
            if self._system_token and time.time() < self._system_token_expires_at:
                return self._system_token
        return self.authenticate()

    def invalidate_system_token(self) -> None:
        with self._token_lock:
            self._system_token = None
            self._system_token_expires_at = 0

    def _request_with_retry(self, method: str, path: str, **kwargs) -> Any:
        try:
            return self._request(method, path, **kwargs)
        except LMSClientError as exc:
            if exc.status_code == 401:
                self.invalidate_system_token()
                return self._request(method, path, **kwargs)
            raise

    def list_books(self, published_only: bool = True) -> List[Dict[str, Any]]:
        params = {"published_only": "true" if published_only else "false"}
        data = self._request_with_retry("GET", "/books", params=params)
        if isinstance(data, dict):
            if "data" in data:
                return data["data"] if isinstance(data["data"], list) else [data["data"]]
            if "books" in data:
                return data["books"] if isinstance(data["books"], list) else [data["books"]]
        if isinstance(data, list):
            return data
        return []

    def grant_access_token(
        self,
        user_id: str,
        book_id: int,
        user_email: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        if ttl_seconds is None:
            ttl_seconds = int(os.getenv("LMS_ACCESS_TOKEN_TTL_SECONDS", "1800"))

        payload: Dict[str, Any] = {
            "user_id": user_id,
            "book_id": book_id,
            "ttl_seconds": ttl_seconds,
        }
        if user_email:
            payload["user_email"] = user_email

        data = self._request_with_retry("POST", "/access-tokens", json=payload)
        if isinstance(data, dict) and "data" in data:
            result = dict(data["data"])
            if "reader" in result:
                result["reader"] = self._normalize_reader_urls(result["reader"])
            result["lms_base_url"] = self.base_url
            return result
        return data if isinstance(data, dict) else {"raw": data}

    def get_access_status(self, user_id: str, book_id: int) -> Dict[str, Any]:
        params = {"user_id": user_id, "book_id": book_id}
        data = self._request_with_retry("GET", "/access-tokens/status", params=params)
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, dict) else {"raw": data}

    def list_access_tokens(
        self,
        user_id: Optional[str] = None,
        book_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if book_id is not None:
            params["book_id"] = book_id

        data = self._request_with_retry("GET", "/access-tokens", params=params or None)
        if isinstance(data, dict):
            if "data" in data:
                return data["data"] if isinstance(data["data"], list) else [data["data"]]
        if isinstance(data, list):
            return data
        return []

    def get_access_token_detail(self, grant_id: int) -> Dict[str, Any]:
        data = self._request_with_retry("GET", f"/access-tokens/{grant_id}")
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data if isinstance(data, dict) else {"raw": data}

    def revoke_active_access(self, user_id: str, book_id: int) -> None:
        params = {"user_id": user_id, "book_id": book_id}
        self._request_with_retry("DELETE", "/access-tokens/active", params=params)

    def revoke_access_token(self, grant_id: int) -> None:
        self._request_with_retry("DELETE", f"/access-tokens/{grant_id}")

    def test_connection(self) -> bool:
        try:
            self.authenticate()
            self.list_books(published_only=True)
            return True
        except Exception as exc:
            logger.warning("LMS connection test failed: %s", exc)
            return False


_lms_client: Optional[LMSClient] = None


def get_lms_client() -> Optional[LMSClient]:
    """Lazy singleton for the LMS client."""
    global _lms_client
    if _lms_client is None:
        try:
            _lms_client = LMSClient()
        except ValueError as exc:
            logger.warning("LMS client not available: %s", exc)
            _lms_client = None
    return _lms_client
