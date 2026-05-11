"""
GitHub API client for fetching repository metadata.

Uses the GitHub REST API to retrieve repository information,
commit activity, issue statistics, and contributor data.

Includes SQLite-based caching to reduce API calls and avoid rate limiting.
GitHub's unauthenticated rate limit is 60 requests/hour, so caching is critical.
"""

import asyncio
import os
import re
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any, Optional

import aiohttp

from dhm.collectors.base import Collector
from dhm.core.exceptions import NetworkError, RateLimitError, RepositoryNotFoundError
from dhm.core.models import RepositoryMetadata

if TYPE_CHECKING:
    from dhm.cache.sqlite import CacheLayer


class GitHubClient(Collector):
    """Async client for GitHub API.

    Fetches repository metadata including stars, forks, commit activity,
    issue statistics, and contributor counts.
    """

    BASE_URL = "https://api.github.com"

    # Cache TTL: 24 hours for GitHub data (metrics don't change frequently)
    CACHE_TTL = 86400  # 24 hours in seconds

    def __init__(
        self,
        session: aiohttp.ClientSession | None = None,
        token: str | None = None,
        timeout: int = 30,
        cache: Optional["CacheLayer"] = None,
    ):
        """Initialize the GitHub client.

        Args:
            session: Optional aiohttp session.
            token: Optional GitHub personal access token for higher rate limits.
            timeout: Request timeout in seconds.
            cache: Optional cache layer for storing API responses.
        """
        super().__init__(session, timeout)
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.cache = cache

    async def fetch(self, identifier: str) -> RepositoryMetadata:
        """Fetch repository metadata from GitHub.

        Args:
            identifier: Repository URL or "owner/repo" string.

        Returns:
            RepositoryMetadata object.
        """
        owner, repo = self.extract_repo_from_url(identifier)
        return await self.get_repository(owner, repo)

    async def get_repository(
        self,
        owner: str,
        repo: str,
    ) -> RepositoryMetadata:
        """Fetch repository metadata.

        Uses cache if available - GitHub data is cached for 24 hours to
        avoid rate limiting (60 requests/hour unauthenticated).

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            RepositoryMetadata with all available metrics.
        """
        # Check cache first
        cache_key = f"github:repo:{owner}/{repo}"
        if self.cache:
            cached = await self.cache.aget_value(cache_key)
            if cached:
                return RepositoryMetadata.from_dict(cached)

        url = f"{self.BASE_URL}/repos/{owner}/{repo}"

        try:
            async with self.session.get(
                url,
                headers=self._build_headers(),
            ) as resp:
                if resp.status == 404:
                    raise RepositoryNotFoundError(f"{owner}/{repo}")
                if resp.status == 403:
                    # Check for rate limiting
                    remaining = resp.headers.get("X-RateLimit-Remaining", "0")
                    if remaining == "0":
                        reset_time = int(resp.headers.get("X-RateLimit-Reset", 0))
                        current_time = int(datetime.now(timezone.utc).timestamp())
                        raise RateLimitError("GitHub", reset_time - current_time)
                    raise NetworkError(url, resp.status, "Access forbidden")
                if resp.status != 200:
                    raise NetworkError(url, resp.status)

                # Check response size before parsing
                self._check_response_size(resp)

                data = await resp.json()

                # Fetch additional metrics in parallel
                commits, issues, prs, contributors = await asyncio.gather(
                    self._get_recent_commits(owner, repo),
                    self._get_issue_stats(owner, repo),
                    self._get_pr_stats(owner, repo),
                    self._get_contributor_count(owner, repo),
                    return_exceptions=True,
                )

                # Handle any exceptions from parallel fetches
                if isinstance(commits, Exception):
                    commits = []
                if isinstance(issues, Exception):
                    issues = {"close_rate": 0.0, "avg_close_time": 0.0}
                if isinstance(prs, Exception):
                    prs = {"merge_rate": 0.0, "avg_merge_time": 0.0, "open_count": 0}
                if isinstance(contributors, Exception):
                    contributors = 0

                metadata = self._build_metadata(data, commits, issues, prs, contributors)

                # Cache the result
                if self.cache:
                    try:
                        await self.cache.aset(cache_key, metadata.to_dict(), self.CACHE_TTL)
                    except Exception:
                        pass  # Don't fail on cache errors

                return metadata

        except aiohttp.ClientError as e:
            raise NetworkError(url, details=str(e))

    async def _get_recent_commits(
        self,
        owner: str,
        repo: str,
        days: int = 30,
    ) -> list[dict[str, Any]]:
        """Get commits from last N days.

        Args:
            owner: Repository owner.
            repo: Repository name.
            days: Number of days to look back.

        Returns:
            List of commit dictionaries.
        """
        since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/commits"
        params = {"since": since, "per_page": 100}

        try:
            async with self.session.get(
                url,
                headers=self._build_headers(),
                params=params,
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                return []
        except aiohttp.ClientError:
            return []

    async def _get_issue_stats(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, float]:
        """Calculate issue resolution statistics.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Dict with close_rate and avg_close_time.
        """
        # Get closed issues from last 90 days
        since = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/issues"

        stats = {"close_rate": 0.0, "avg_close_time": 0.0}

        try:
            # Get open issues
            async with self.session.get(
                url,
                headers=self._build_headers(),
                params={"state": "open", "per_page": 100},
            ) as resp:
                if resp.status != 200:
                    return stats
                open_issues = await resp.json()

            # Get closed issues
            async with self.session.get(
                url,
                headers=self._build_headers(),
                params={"state": "closed", "since": since, "per_page": 100},
            ) as resp:
                if resp.status != 200:
                    return stats
                closed_issues = await resp.json()

            # Filter out pull requests (they appear in issues API)
            open_issues = [i for i in open_issues if "pull_request" not in i]
            closed_issues = [i for i in closed_issues if "pull_request" not in i]

            total = len(open_issues) + len(closed_issues)
            if total > 0:
                stats["close_rate"] = len(closed_issues) / total

            # Calculate average close time
            close_times = []
            for issue in closed_issues:
                created = issue.get("created_at")
                closed = issue.get("closed_at")
                if created and closed:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        closed_dt = datetime.fromisoformat(closed.replace("Z", "+00:00"))
                        close_times.append((closed_dt - created_dt).days)
                    except (ValueError, TypeError):
                        pass

            if close_times:
                stats["avg_close_time"] = sum(close_times) / len(close_times)

        except aiohttp.ClientError:
            pass

        return stats

    async def _get_pr_stats(
        self,
        owner: str,
        repo: str,
    ) -> dict[str, Any]:
        """Calculate pull request statistics.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Dict with merge_rate, avg_merge_time, and open_count.
        """
        # Note: 90-day window for PR analysis (variable available for future filtering)
        _ = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/pulls"

        stats: dict[str, Any] = {"merge_rate": 0.0, "avg_merge_time": 0.0, "open_count": 0}

        try:
            # Get open PRs
            async with self.session.get(
                url,
                headers=self._build_headers(),
                params={"state": "open", "per_page": 100},
            ) as resp:
                if resp.status != 200:
                    return stats
                open_prs = await resp.json()
                stats["open_count"] = len(open_prs)

            # Get closed/merged PRs
            async with self.session.get(
                url,
                headers=self._build_headers(),
                params={"state": "closed", "per_page": 100},
            ) as resp:
                if resp.status != 200:
                    return stats
                closed_prs = await resp.json()

            # Count merged PRs
            merged_prs = [pr for pr in closed_prs if pr.get("merged_at")]

            total = len(open_prs) + len(closed_prs)
            if total > 0:
                stats["merge_rate"] = len(merged_prs) / total

            # Calculate average merge time
            merge_times = []
            for pr in merged_prs:
                created = pr.get("created_at")
                merged = pr.get("merged_at")
                if created and merged:
                    try:
                        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                        merged_dt = datetime.fromisoformat(merged.replace("Z", "+00:00"))
                        merge_times.append((merged_dt - created_dt).days)
                    except (ValueError, TypeError):
                        pass

            if merge_times:
                stats["avg_merge_time"] = sum(merge_times) / len(merge_times)

        except aiohttp.ClientError:
            pass

        return stats

    async def _get_contributor_count(
        self,
        owner: str,
        repo: str,
    ) -> int:
        """Get the number of contributors.

        Args:
            owner: Repository owner.
            repo: Repository name.

        Returns:
            Number of contributors.
        """
        url = f"{self.BASE_URL}/repos/{owner}/{repo}/contributors"

        try:
            async with self.session.get(
                url,
                headers=self._build_headers(),
                params={"per_page": 1, "anon": "true"},
            ) as resp:
                if resp.status != 200:
                    return 0

                # GitHub returns total count in Link header
                link_header = resp.headers.get("Link", "")
                if "last" in link_header:
                    # Parse the last page number from Link header
                    match = re.search(r'page=(\d+)>; rel="last"', link_header)
                    if match:
                        return int(match.group(1))

                # If no pagination, count the returned contributors
                contributors = await resp.json()
                return len(contributors)

        except aiohttp.ClientError:
            return 0

    def _build_metadata(
        self,
        data: dict[str, Any],
        commits: list[dict[str, Any]],
        issues: dict[str, float],
        prs: dict[str, Any],
        contributors: int,
    ) -> RepositoryMetadata:
        """Build RepositoryMetadata from collected data.

        Args:
            data: Repository data from GitHub API.
            commits: Recent commits list.
            issues: Issue statistics.
            prs: Pull request statistics.
            contributors: Contributor count.

        Returns:
            RepositoryMetadata object.
        """
        # Parse dates
        last_commit_date = None
        if commits and commits[0].get("commit", {}).get("committer", {}).get("date"):
            try:
                date_str = commits[0]["commit"]["committer"]["date"]
                last_commit_date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                pass

        created_date = None
        if data.get("created_at"):
            try:
                created_date = datetime.fromisoformat(
                    data["created_at"].replace("Z", "+00:00")
                )
            except (ValueError, TypeError):
                pass

        # Calculate commit frequency (commits per day in last 30 days)
        commit_frequency = len(commits) / 30.0 if commits else 0.0

        return RepositoryMetadata(
            url=data.get("html_url", ""),
            stars=data.get("stargazers_count", 0),
            forks=data.get("forks_count", 0),
            open_issues=data.get("open_issues_count", 0),
            open_pull_requests=prs.get("open_count", 0),
            watchers=data.get("subscribers_count", 0),
            contributors_count=contributors,
            last_commit_date=last_commit_date,
            created_date=created_date,
            is_archived=data.get("archived", False),
            is_fork=data.get("fork", False),
            license=data.get("license", {}).get("spdx_id") if data.get("license") else None,
            topics=data.get("topics", []),
            default_branch=data.get("default_branch", "main"),
            commit_frequency_30d=commit_frequency,
            issue_close_rate_90d=issues.get("close_rate", 0.0),
            pr_merge_rate_90d=prs.get("merge_rate", 0.0),
            avg_issue_close_time_days=issues.get("avg_close_time", 0.0),
            avg_pr_merge_time_days=prs.get("avg_merge_time", 0.0),
        )

    def extract_repo_from_url(self, url: str) -> tuple[str, str]:
        """Extract owner/repo from GitHub URL.

        Args:
            url: GitHub URL or "owner/repo" string.

        Returns:
            Tuple of (owner, repo).

        Raises:
            ValueError: If the URL cannot be parsed.
        """
        # Handle simple "owner/repo" format
        if "/" in url and "://" not in url and "@" not in url:
            parts = url.strip("/").split("/")
            if len(parts) >= 2:
                return parts[0], parts[1].replace(".git", "")

        # Handle various URL formats
        patterns = [
            r"github\.com/([^/]+)/([^/]+?)(?:\.git)?/?$",
            r"github\.com/([^/]+)/([^/]+?)(?:/.*)?$",
            r"github\.com:([^/]+)/([^/]+?)(?:\.git)?$",
        ]

        for pattern in patterns:
            if match := re.search(pattern, url):
                owner, repo = match.groups()
                return owner, repo.replace(".git", "")

        raise ValueError(f"Cannot parse GitHub URL: {url}")

    def _build_headers(self) -> dict[str, str]:
        """Build request headers for GitHub API."""
        headers = {
            "User-Agent": "DependencyHealthMonitor/0.1.0",
            "Accept": "application/vnd.github.v3+json",
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
