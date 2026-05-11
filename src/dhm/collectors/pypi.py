"""
PyPI API client for fetching package metadata.

Uses the PyPI JSON API to retrieve package information, release history,
and download statistics.

Includes caching to reduce redundant API calls.
"""

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

import aiohttp

from dhm.collectors.base import Collector
from dhm.core.exceptions import NetworkError, PackageNotFoundError, RateLimitError
from dhm.core.models import PyPIMetadata
from dhm.core.validation import encode_package_name_for_url

if TYPE_CHECKING:
    from dhm.cache.sqlite import CacheLayer


class PyPIClient(Collector):
    """Async client for PyPI JSON API.

    Fetches package metadata including versions, release dates,
    project URLs, and dependency information.
    """

    BASE_URL = "https://pypi.org/pypi"

    # Cache TTL: 1 hour for PyPI data (releases are relatively infrequent)
    CACHE_TTL = 3600  # 1 hour in seconds
    # Download stats can be cached longer (6 hours) since they update daily
    DOWNLOAD_CACHE_TTL = 21600  # 6 hours

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        timeout: int = 30,
        cache: "CacheLayer | None" = None,
    ):
        """Initialize the PyPI client.

        Args:
            session: Optional aiohttp session.
            timeout: Request timeout in seconds.
            cache: Optional cache layer for storing API responses.
        """
        super().__init__(session, timeout)
        self.cache = cache

    async def fetch(self, identifier: str) -> PyPIMetadata:
        """Fetch package metadata from PyPI.

        Args:
            identifier: Package name.

        Returns:
            PyPIMetadata object.

        Raises:
            PackageNotFoundError: If the package doesn't exist.
            NetworkError: If the request fails.
        """
        return await self.get_package_info(identifier)

    async def get_package_info(
        self,
        name: str,
        version: str | None = None,
    ) -> PyPIMetadata:
        """Fetch package metadata from PyPI.

        Uses cache if available to reduce API calls.

        Args:
            name: Package name.
            version: Optional specific version to fetch.

        Returns:
            PyPIMetadata object with package information.

        Raises:
            PackageNotFoundError: If the package doesn't exist.
            NetworkError: If the request fails.
        """
        # Check cache first
        cache_key = f"pypi:pkg:{name}:{version or 'latest'}"
        if self.cache:
            cached = await self.cache.aget_value(cache_key)
            if cached:
                return PyPIMetadata.from_dict(cached)

        # URL-encode the package name to prevent injection
        encoded_name = encode_package_name_for_url(name)
        if version:
            encoded_version = encode_package_name_for_url(version)
            url = f"{self.BASE_URL}/{encoded_name}/{encoded_version}/json"
        else:
            url = f"{self.BASE_URL}/{encoded_name}/json"

        try:
            status, data = await self._get_json(url, headers=self._build_headers())

            if status == 404:
                raise PackageNotFoundError(name)
            if status == 429:
                raise RateLimitError("PyPI")
            if status != 200:
                raise NetworkError(url, status)

            metadata = self._parse_response(data)

            # Cache the result
            if self.cache:
                try:
                    await self.cache.aset(cache_key, metadata.to_dict(), self.CACHE_TTL)
                except Exception:
                    pass  # Don't fail on cache errors

            return metadata

        except aiohttp.ClientError as e:
            raise NetworkError(url, details=str(e))

    async def get_release_history(self, name: str) -> list[dict[str, Any]]:
        """Get all releases with dates.

        Args:
            name: Package name.

        Returns:
            List of release dictionaries with version and upload_time.
        """
        encoded_name = encode_package_name_for_url(name)
        url = f"{self.BASE_URL}/{encoded_name}/json"

        try:
            status, data = await self._get_json(url, headers=self._build_headers())

            if status == 404:
                raise PackageNotFoundError(name)
            if status != 200:
                raise NetworkError(url, status)

            releases = []

            for version, files in data.get("releases", {}).items():
                if files:  # Skip yanked/empty releases
                    releases.append({
                        "version": version,
                        "upload_time": files[0].get("upload_time"),
                        "yanked": files[0].get("yanked", False),
                    })

            return sorted(
                releases,
                key=lambda r: r.get("upload_time", ""),
                reverse=True,
            )

        except aiohttp.ClientError as e:
            raise NetworkError(url, details=str(e))

    async def get_latest_version(self, name: str) -> str:
        """Get the latest version of a package.

        Args:
            name: Package name.

        Returns:
            Latest version string.
        """
        info = await self.get_package_info(name)
        return info.version

    def _parse_response(self, data: dict[str, Any]) -> PyPIMetadata:
        """Parse PyPI JSON response into PyPIMetadata.

        Args:
            data: Raw JSON response from PyPI.

        Returns:
            PyPIMetadata object.
        """
        info = data.get("info", {})
        releases = data.get("releases", {})

        # Calculate download stats
        downloads = self._estimate_downloads(data)

        # Get release dates
        release_date = self._parse_release_date(releases, info.get("version", ""))
        first_release_date = self._find_first_release(releases)

        # Count yanked releases
        yanked_count = self._count_yanked(releases)

        return PyPIMetadata(
            name=info.get("name", ""),
            version=info.get("version", ""),
            summary=info.get("summary", "") or "",
            author=info.get("author", "") or "",
            author_email=info.get("author_email"),
            license=info.get("license"),
            python_requires=info.get("requires_python"),
            requires_dist=info.get("requires_dist") or [],
            project_urls=info.get("project_urls") or {},
            classifiers=info.get("classifiers") or [],
            downloads_last_month=downloads,
            release_date=release_date,
            first_release_date=first_release_date,
            total_releases=len(releases),
            yanked_releases=yanked_count,
        )

    def _estimate_downloads(self, data: dict[str, Any]) -> int:
        """Estimate monthly downloads from available data.

        PyPI doesn't provide download stats directly. We return 0 here
        and fetch from pypistats.org separately in get_download_stats().
        """
        return 0

    async def get_download_stats(self, name: str) -> int:
        """Fetch download statistics from pypistats.org API.

        Uses cache (6 hours TTL) since download stats update daily.

        Args:
            name: Package name.

        Returns:
            Downloads in the last month, or 0 if unavailable.
        """
        # Check cache first
        cache_key = f"pypistats:downloads:{name}"
        if self.cache:
            cached = await self.cache.aget_value(cache_key)
            if cached is not None:
                return cached

        encoded_name = encode_package_name_for_url(name)
        url = f"https://pypistats.org/api/packages/{encoded_name}/recent"

        try:
            status, data = await self._get_json(url, headers=self._build_headers())

            if status != 200:
                return 0

            # pypistats returns {"data": {"last_month": 12345, ...}}
            downloads = data.get("data", {}).get("last_month", 0)

            # Cache the result
            if self.cache:
                try:
                    await self.cache.aset(cache_key, downloads, self.DOWNLOAD_CACHE_TTL)
                except Exception:
                    pass

            return downloads

        except Exception:
            return 0

    def _parse_release_date(
        self,
        releases: dict[str, list],
        version: str,
    ) -> datetime | None:
        """Parse the release date for a specific version.

        Args:
            releases: Release data from PyPI.
            version: Version to get date for.

        Returns:
            datetime or None if not found.
        """
        if version not in releases or not releases[version]:
            return None

        files = releases[version]
        for file in files:
            if upload_time := file.get("upload_time"):
                try:
                    dt = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    return dt
                except (ValueError, TypeError):
                    pass

        return None

    def _find_first_release(
        self,
        releases: dict[str, list],
    ) -> datetime | None:
        """Find the date of the first release.

        Args:
            releases: Release data from PyPI.

        Returns:
            datetime of first release or None.
        """
        earliest: datetime | None = None

        for version, files in releases.items():
            if not files:
                continue

            for file in files:
                if upload_time := file.get("upload_time"):
                    try:
                        dt = datetime.fromisoformat(upload_time.replace("Z", "+00:00"))
                        if dt.tzinfo is None:
                            dt = dt.replace(tzinfo=timezone.utc)
                        if earliest is None or dt < earliest:
                            earliest = dt
                    except (ValueError, TypeError):
                        pass

        return earliest

    def _count_yanked(self, releases: dict[str, list]) -> int:
        """Count number of yanked releases.

        Args:
            releases: Release data from PyPI.

        Returns:
            Count of yanked releases.
        """
        count = 0
        for version, files in releases.items():
            if files and files[0].get("yanked", False):
                count += 1
        return count

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for PyPI."""
        return {
            "User-Agent": "DependencyHealthMonitor/0.1.0",
            "Accept": "application/json",
        }
