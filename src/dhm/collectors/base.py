"""
Abstract base class for data collectors.

Defines the interface that all collectors must implement.
"""

import asyncio
import json
import logging
import random
from abc import ABC, abstractmethod
from typing import Any

import aiohttp

from dhm.core.exceptions import ValidationError
from dhm.core.validation import MAX_RESPONSE_SIZE, validate_response_size

logger = logging.getLogger(__name__)


class Collector(ABC):
    """Abstract base class for data collectors.

    All collectors share common functionality like session management
    and error handling. Specific collectors implement the fetch methods
    for their respective data sources.
    """

    # Maximum response size (10 MB) - can be overridden by subclasses
    MAX_RESPONSE_SIZE = MAX_RESPONSE_SIZE

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 30,
    ):
        """Initialize the collector.

        Args:
            session: Optional aiohttp session. If not provided, one will
                     be created when needed.
            timeout: Request timeout in seconds.
        """
        self._session = session
        self._owns_session = session is None
        self.timeout = aiohttp.ClientTimeout(total=timeout)

    @property
    def session(self) -> aiohttp.ClientSession:
        """Get or create the aiohttp session."""
        if self._session is None:
            self._session = aiohttp.ClientSession(timeout=self.timeout)
            self._owns_session = True
        return self._session

    async def close(self) -> None:
        """Close the session if we own it."""
        if self._owns_session and self._session is not None:
            await self._session.close()
            self._session = None

    async def __aenter__(self) -> "Collector":
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Async context manager exit."""
        await self.close()

    @abstractmethod
    async def fetch(self, identifier: str) -> Any:
        """Fetch data for the given identifier.

        Args:
            identifier: The package name, repository URL, or other identifier.

        Returns:
            The fetched data, specific to each collector type.

        Raises:
            DHMError: If the fetch fails.
        """
        pass

    def _build_headers(self) -> dict[str, str]:
        """Build common request headers.

        Override in subclasses to add authentication or other headers.
        """
        return {
            "User-Agent": "DependencyHealthMonitor/0.1.0",
            "Accept": "application/json",
        }

    def _check_response_size(self, response: aiohttp.ClientResponse) -> None:
        """Check if response size is within acceptable limits.

        Args:
            response: The aiohttp response object.

        Raises:
            ValidationError: If the response is too large.
        """
        content_length = response.headers.get("Content-Length")
        if content_length is not None:
            try:
                validate_response_size(int(content_length), self.MAX_RESPONSE_SIZE)
            except ValueError:
                pass  # Invalid Content-Length header, proceed with caution

    async def _get_json(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> tuple[int, Any]:
        """Fetch a URL and return (status_code, parsed_json_body).

        Implements retry-with-exponential-backoff for transient failures:
          - Retries on: ClientConnectionError, ServerDisconnectedError,
            ClientPayloadError, asyncio.TimeoutError, HTTP 5xx.
          - Does NOT retry on 4xx except 429.
          - On 429, honours the ``Retry-After`` header (integer seconds)
            or falls back to exponential backoff.
          - Max 3 attempts (initial + 2 retries). Base delays: 1 s, 2 s
            with ±20 % jitter.
          - Enforces MAX_RESPONSE_SIZE on the actual body bytes (M-6)
            in addition to the Content-Length pre-check.

        Args:
            url: The URL to fetch.
            headers: Optional request headers.

        Returns:
            Tuple of (HTTP status code, parsed JSON body).  Callers are
            responsible for interpreting non-200 status codes.

        Raises:
            ValidationError: If the response body exceeds MAX_RESPONSE_SIZE.
            aiohttp.ClientError: After all retries are exhausted.
            asyncio.TimeoutError: After all retries are exhausted.
        """
        max_attempts = 3
        base_delays = [1.0, 2.0]  # seconds between attempt 1→2 and 2→3

        _transient_exc = (
            aiohttp.ClientConnectionError,
            aiohttp.ServerDisconnectedError,
            aiohttp.ClientPayloadError,
            asyncio.TimeoutError,
        )

        last_exc: BaseException | None = None

        for attempt in range(1, max_attempts + 1):
            try:
                async with self.session.get(url, headers=headers or {}) as response:
                    status = response.status

                    # --- Content-Length pre-check (early bail) ---
                    self._check_response_size(response)

                    # --- Decide whether to retry on this status ---
                    if status == 429:
                        if attempt < max_attempts:
                            retry_after_hdr = response.headers.get("Retry-After")
                            if retry_after_hdr is not None:
                                try:
                                    delay = float(retry_after_hdr)
                                except ValueError:
                                    delay = base_delays[attempt - 1]
                            else:
                                delay = base_delays[attempt - 1]
                            delay *= 1 + random.uniform(-0.2, 0.2)  # ±20 % jitter
                            logger.warning(
                                "Retry %d/%d for %s after 429 (wait %.1fs)",
                                attempt,
                                max_attempts,
                                url,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue  # retry

                    if 500 <= status < 600:
                        if attempt < max_attempts:
                            delay = base_delays[attempt - 1]
                            delay *= 1 + random.uniform(-0.2, 0.2)
                            logger.warning(
                                "Retry %d/%d for %s after HTTP %d (wait %.1fs)",
                                attempt,
                                max_attempts,
                                url,
                                status,
                                delay,
                            )
                            await asyncio.sleep(delay)
                            continue  # retry

                    # --- Read the FULL body with a hard byte cap (M-6) ---
                    # NOTE: StreamReader.read(n) returns *up to* n bytes and may
                    # return a partial prefix when the body spans multiple TCP
                    # chunks, which truncated JSON and caused intermittent
                    # JSONDecodeErrors. Iterate to EOF, enforcing the cap while
                    # streaming so memory stays bounded.
                    max_bytes = self.MAX_RESPONSE_SIZE
                    total = 0
                    chunks: list[bytes] = []
                    async for chunk in response.content.iter_chunked(65536):
                        total += len(chunk)
                        if total > max_bytes:
                            raise ValidationError(
                                "response_size",
                                f"{total} bytes",
                                f"Response body exceeded {max_bytes} bytes",
                            )
                        chunks.append(chunk)
                    data = json.loads(b"".join(chunks))
                    return status, data

            except _transient_exc as exc:
                last_exc = exc
                if attempt < max_attempts:
                    delay = base_delays[attempt - 1]
                    delay *= 1 + random.uniform(-0.2, 0.2)
                    logger.warning(
                        "Retry %d/%d for %s after %s: %s (wait %.1fs)",
                        attempt,
                        max_attempts,
                        url,
                        type(exc).__name__,
                        exc,
                        delay,
                    )
                    await asyncio.sleep(delay)
                else:
                    raise

        # Should only be reached if max_attempts == 0 (never in practice)
        if last_exc is not None:
            raise last_exc
        raise RuntimeError("_get_json: unreachable")
