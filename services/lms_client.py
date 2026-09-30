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
        for key in ("first_page_url", "search_url"):
            if key in normalized and normalized[key]:
                normalized[key] = self.absolute_url(normalized[key])
        if normalized.get("cover_url") and str(normalized["cover_url"]).startswith("/books/"):
            edition_id = normalized.get("edition_reference_id") or normalized.get("book_reference_id")
            if edition_id:
                from config import hub_edition_cover_url

                normalized["cover_url"] = hub_edition_cover_url(str(edition_id))
        elif normalized.get("cover_url") and normalized["cover_url"].startswith("http"):
            if self.base_url in str(normalized["cover_url"]) and "/cover" in str(normalized["cover_url"]):
                edition_id = normalized.get("edition_reference_id") or normalized.get("book_reference_id")
                if edition_id:
                    from config import hub_edition_cover_url

                    normalized["cover_url"] = hub_edition_cover_url(str(edition_id))
        return normalized

    def _reader_urls_for_edition(self, edition_reference_id: str) -> Dict[str, Any]:
        """
        LMS reader routes use the edition/version UUID in the path segment:
        GET /books/{edition_reference_id}/pages/1
        (same id as store `edition_reference_id`, not always the parent book UUID).
        """
        from config import hub_edition_cover_url

        edition_id = str(edition_reference_id)
        reader = {
            "book_reference_id": edition_id,
            "edition_reference_id": edition_id,
            "version_reference_id": edition_id,
            "cover_url": hub_edition_cover_url(edition_id),
            "first_page_url": f"/books/{edition_id}/pages/1",
            "search_url": f"/books/{edition_id}/search",
        }
        return self._normalize_reader_urls(reader)

    def _apply_edition_reader_paths(
        self,
        grant: Dict[str, Any],
        edition_reference_id: str,
    ) -> Dict[str, Any]:
        edition_id = str(edition_reference_id)
        grant = dict(grant)
        grant["edition_reference_id"] = edition_id
        grant["reader"] = self._reader_urls_for_edition(edition_id)
        return grant

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
            data = response.json()
        except ValueError:
            return response.text

        if isinstance(data, dict) and data.get("success") is False:
            raise LMSClientError(
                data.get("message") or "LMS request failed",
                status_code=response.status_code if response.status_code >= 400 else 400,
                response_body=data,
            )
        return data

    @staticmethod
    def _extract_access_token(data: Any) -> Optional[str]:
        if not isinstance(data, dict):
            return None
        if data.get("access_token"):
            return str(data["access_token"])
        inner = LMSClient._unwrap_payload(data)
        if isinstance(inner, dict) and inner.get("access_token"):
            return str(inner["access_token"])
        return None

    @staticmethod
    def _extract_expires_in(data: Any, default: int = 900) -> int:
        if not isinstance(data, dict):
            return default
        for source in (data, LMSClient._unwrap_payload(data) if isinstance(LMSClient._unwrap_payload(data), dict) else {}):
            if isinstance(source, dict) and source.get("expires_in"):
                try:
                    return int(source["expires_in"])
                except (TypeError, ValueError):
                    pass
        return default

    @retry_on_failure(max_retries=2, delay=1)
    def authenticate(self) -> str:
        """Obtain a short-lived system JWT via client_credentials grant."""
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        data = self._request("POST", "/oauth/token", json=payload, use_system_auth=False)

        access_token = self._extract_access_token(data)
        if not access_token:
            raise LMSClientError("LMS OAuth response missing access_token", response_body=data)

        expires_in = self._extract_expires_in(data)

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

    @staticmethod
    def _unwrap_payload(data: Any) -> Any:
        if isinstance(data, dict) and "data" in data:
            return data["data"]
        return data

    @staticmethod
    def _is_uuid_reference(value: Any) -> bool:
        if value is None:
            return False
        text = str(value).strip()
        return len(text) >= 32 and "-" in text

    @staticmethod
    def _book_reference_id(book: Dict[str, Any]) -> Optional[str]:
        """LMS access APIs require book UUID (`reference_id`), not legacy numeric ids."""
        for key in ("reference_id", "book_reference_id"):
            value = book.get(key)
            if value is not None and str(value).strip():
                text = str(value).strip()
                if LMSClient._is_uuid_reference(text):
                    return text
        value = book.get("id")
        if LMSClient._is_uuid_reference(value):
            return str(value).strip()
        return None

    @staticmethod
    def _version_reference_id(version: Dict[str, Any]) -> Optional[str]:
        for key in ("version_reference_id", "edition_reference_id", "reference_id", "id"):
            value = version.get(key)
            if value is not None and str(value).strip():
                return str(value)
        return None

    @staticmethod
    def _as_list(data: Any) -> List[Dict[str, Any]]:
        result = LMSClient._unwrap_payload(data)
        if isinstance(result, list):
            return [item for item in result if isinstance(item, dict)]
        if isinstance(result, dict):
            for key in ("versions", "editions", "items", "books"):
                if key in result and isinstance(result[key], list):
                    return [item for item in result[key] if isinstance(item, dict)]
            return [result]
        return []

    def list_book_versions(self, book_reference_id: str) -> List[Dict[str, Any]]:
        """GET /books/{book_reference_id}/versions"""
        from urllib.parse import quote

        encoded = quote(str(book_reference_id), safe="")
        data = self._request_with_retry("GET", f"/books/{encoded}/versions")
        return self._as_list(data)

    def get_book_version(self, book_reference_id: str, version_reference_id: str) -> Dict[str, Any]:
        """GET /books/{book_reference_id}/versions/{version_reference_id}"""
        from urllib.parse import quote

        book_encoded = quote(str(book_reference_id), safe="")
        version_encoded = quote(str(version_reference_id), safe="")
        data = self._request_with_retry(
            "GET",
            f"/books/{book_encoded}/versions/{version_encoded}",
        )
        result = self._unwrap_payload(data)
        if isinstance(result, dict):
            result.setdefault("book_reference_id", str(book_reference_id))
            result.setdefault("version_reference_id", str(version_reference_id))
            return result
        return {"raw": result}

    def get_edition(
        self,
        edition_reference_id: str,
        book_reference_id_hint: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Resolve a book version/edition by its version UUID.

        African Hub LMS exposes versions at
        GET /books/{book_reference_id}/versions/{version_reference_id}
        not /editions/{id}. When only the version id is known, scan the catalog.
        """
        version_id = str(edition_reference_id)
        if book_reference_id_hint and self._is_uuid_reference(book_reference_id_hint):
            try:
                edition = self.get_book_version(str(book_reference_id_hint), version_id)
                if isinstance(edition, dict):
                    edition = dict(edition)
                    edition.setdefault("book_reference_id", str(book_reference_id_hint))
                    edition.setdefault("version_reference_id", version_id)
                    edition.setdefault("edition_reference_id", version_id)
                    if "book" not in edition:
                        from urllib.parse import quote

                        book_encoded = quote(str(book_reference_id_hint), safe="")
                        book_data = self._unwrap_payload(
                            self._request_with_retry("GET", f"/books/{book_encoded}")
                        )
                        if isinstance(book_data, dict):
                            edition["book"] = book_data
                    return edition
            except LMSClientError:
                pass

        books = self.list_books(published_only=False)
        for book in books:
            book_ref = self._book_reference_id(book)
            if not book_ref:
                continue
            for version in self.list_book_versions(book_ref):
                if self._version_reference_id(version) == version_id:
                    edition = dict(version)
                    edition["book_reference_id"] = book_ref
                    edition["book"] = book
                    edition.setdefault("version_reference_id", version_id)
                    edition.setdefault("edition_reference_id", version_id)
                    return edition

        raise LMSClientError(
            f"Edition {version_id} not found in LMS catalog",
            status_code=404,
        )

    def build_edition_index(self, published_only: bool = False) -> Dict[str, Dict[str, Any]]:
        """Map edition/version UUID → full edition payload (includes nested `book`)."""
        index: Dict[str, Dict[str, Any]] = {}
        for edition in self.list_editions(published_only=published_only):
            ref = self._version_reference_id(edition)
            if ref:
                index[ref] = edition
        return index

    def list_editions(
        self,
        book_reference_id: Optional[str] = None,
        published_only: bool = False,
    ) -> List[Dict[str, Any]]:
        """List book versions (editions), optionally for one book."""
        if book_reference_id:
            versions = self.list_book_versions(book_reference_id)
        else:
            versions = []
            for book in self.list_books(published_only=published_only):
                book_ref = self._book_reference_id(book)
                if not book_ref:
                    continue
                for version in self.list_book_versions(book_ref):
                    item = dict(version)
                    item["book_reference_id"] = book_ref
                    item["book"] = book
                    versions.append(item)
        return versions

    def list_books(self, published_only: bool = True) -> List[Dict[str, Any]]:
        params = {"published_only": "true" if published_only else "false"}
        data = self._request_with_retry("GET", "/books", params=params)
        return self._as_list(data)

    def grant_access_token(
        self,
        user_id: str,
        book_reference_id: str,
        user_email: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
        version_reference_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        if ttl_seconds is None:
            ttl_seconds = int(os.getenv("LMS_ACCESS_TOKEN_TTL_SECONDS", "1800"))

        payload: Dict[str, Any] = {
            "user_id": user_id,
            "book_reference_id": str(book_reference_id),
            "ttl_seconds": ttl_seconds,
        }
        if user_email:
            payload["user_email"] = user_email
        if version_reference_id:
            version_id = str(version_reference_id)
            payload["version_reference_id"] = version_id
            payload["edition_reference_id"] = version_id

        data = self._request_with_retry("POST", "/access-tokens", json=payload)
        return self._normalize_grant_response(
            data,
            book_reference_id=str(book_reference_id),
            edition_reference_id=str(version_reference_id) if version_reference_id else None,
        )

    def _normalize_grant_response(
        self,
        data: Any,
        *,
        book_reference_id: str,
        edition_reference_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        result = self._unwrap_payload(data)
        if isinstance(result, dict):
            result = dict(result)
            if "reader" in result:
                reader = dict(result["reader"]) if isinstance(result["reader"], dict) else result["reader"]
                if isinstance(reader, dict):
                    reader.setdefault("book_reference_id", book_reference_id)
                    if edition_reference_id:
                        reader.setdefault("edition_reference_id", edition_reference_id)
                        reader.setdefault("version_reference_id", edition_reference_id)
                    result["reader"] = self._normalize_reader_urls(reader)
            result["lms_base_url"] = self.base_url
            result["book_reference_id"] = book_reference_id
            if edition_reference_id:
                result["edition_reference_id"] = edition_reference_id
            return result
        return data if isinstance(data, dict) else {"raw": data}

    def grant_access_for_paid_edition(
        self,
        user_id: str,
        edition_reference_id: str,
        user_email: Optional[str] = None,
        ttl_seconds: Optional[int] = None,
    ) -> Dict[str, Any]:
        """
        Issue a reading token for a purchased edition.

        African Hub LMS serves pages at `/books/{edition_reference_id}/pages/{n}`.
        The access-token request uses that same edition UUID as `book_reference_id`.
        """
        edition_id = str(edition_reference_id)

        parent_book_ref = None
        try:
            edition = self.get_edition(edition_id)
            parent_book_ref = edition.get("book_reference_id")
            if not parent_book_ref and isinstance(edition.get("book"), dict):
                parent_book_ref = self._book_reference_id(edition["book"])
        except LMSClientError:
            edition = None

        try:
            grant = self.grant_access_token(
                user_id=user_id,
                book_reference_id=edition_id,
                user_email=user_email,
                ttl_seconds=ttl_seconds,
            )
        except LMSClientError as first_error:
            if parent_book_ref and self._is_uuid_reference(parent_book_ref):
                grant = self.grant_access_token(
                    user_id=user_id,
                    book_reference_id=str(parent_book_ref),
                    user_email=user_email,
                    ttl_seconds=ttl_seconds,
                    version_reference_id=edition_id,
                )
            else:
                raise first_error

        grant = self._apply_edition_reader_paths(grant, edition_id)
        grant["lms_base_url"] = self.base_url
        if parent_book_ref:
            grant["parent_book_reference_id"] = parent_book_ref
        return grant

    def _parent_book_ref_for_edition(self, edition_reference_id: str) -> Optional[str]:
        try:
            edition = self.get_edition(str(edition_reference_id))
        except LMSClientError:
            return None
        parent = edition.get("book_reference_id")
        if not parent and isinstance(edition.get("book"), dict):
            parent = self._book_reference_id(edition["book"])
        if parent and self._is_uuid_reference(parent):
            return str(parent)
        return None

    def get_access_status_for_paid_edition(
        self,
        user_id: str,
        edition_reference_id: str,
    ) -> Dict[str, Any]:
        edition_id = str(edition_reference_id)
        try:
            return self.get_access_status(user_id, edition_id)
        except LMSClientError as first_error:
            parent = self._parent_book_ref_for_edition(edition_id)
            if parent and parent != edition_id:
                return self.get_access_status(user_id, parent)
            raise first_error

    def revoke_access_for_paid_edition(
        self,
        user_id: str,
        edition_reference_id: str,
    ) -> Dict[str, Any]:
        """
        Revoke active LMS session token(s) for a purchased edition.
        Tries edition UUID first (reader path id), then parent book UUID if different.
        """
        edition_id = str(edition_reference_id)
        revoked = []
        errors: List[str] = []

        for ref in (edition_id, self._parent_book_ref_for_edition(edition_id)):
            if not ref or ref in revoked:
                continue
            try:
                self.revoke_active_access(user_id, ref)
                revoked.append(ref)
            except LMSClientError as exc:
                if exc.status_code != 404:
                    errors.append(str(exc))

        if not revoked and errors:
            raise LMSClientError(errors[0], status_code=502)

        return {
            "user_id": user_id,
            "edition_reference_id": edition_id,
            "revoked_book_reference_ids": revoked,
        }

    def fetch_cover_image(self, reference_id: str) -> tuple:
        """GET /books/{reference_id}/cover — returns (bytes, content_type)."""
        from urllib.parse import quote

        encoded = quote(str(reference_id).strip(), safe="")
        url = f"{self.base_url}/books/{encoded}/cover"
        headers = {"Authorization": f"Bearer {self.get_system_token()}"}
        try:
            response = requests.get(url, headers=headers, timeout=60)
        except requests.exceptions.RequestException as exc:
            raise LMSClientError(f"LMS cover fetch failed: {exc}", status_code=502) from exc

        if response.status_code >= 400:
            body: Any
            try:
                body = response.json()
            except ValueError:
                body = response.text
            raise LMSClientError(
                f"LMS cover error ({response.status_code})",
                status_code=response.status_code,
                response_body=body,
            )

        content_type = response.headers.get("Content-Type", "image/jpeg")
        return response.content, content_type

    def fetch_cover_for_edition(self, edition_reference_id: str) -> tuple:
        """Prefer edition UUID path; fall back to parent book UUID from catalog."""
        edition_id = str(edition_reference_id)
        try:
            return self.fetch_cover_image(edition_id)
        except LMSClientError as first_error:
            parent = self._parent_book_ref_for_edition(edition_id)
            if parent and parent != edition_id:
                try:
                    return self.fetch_cover_image(parent)
                except LMSClientError:
                    pass
            raise first_error

    def get_access_status(self, user_id: str, book_reference_id: str) -> Dict[str, Any]:
        params = {"user_id": user_id, "book_reference_id": str(book_reference_id)}
        data = self._request_with_retry("GET", "/access-tokens/status", params=params)
        result = self._unwrap_payload(data)
        return result if isinstance(result, dict) else {"raw": result}

    def list_access_tokens(
        self,
        user_id: Optional[str] = None,
        book_reference_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {}
        if user_id:
            params["user_id"] = user_id
        if book_reference_id is not None:
            params["book_reference_id"] = str(book_reference_id)

        data = self._request_with_retry("GET", "/access-tokens", params=params or None)
        return self._as_list(data)

    def get_access_token_detail(self, grant_id: int) -> Dict[str, Any]:
        data = self._request_with_retry("GET", f"/access-tokens/{grant_id}")
        result = self._unwrap_payload(data)
        return result if isinstance(result, dict) else {"raw": result}

    def revoke_active_access(self, user_id: str, book_reference_id: str) -> None:
        params = {"user_id": user_id, "book_reference_id": str(book_reference_id)}
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
