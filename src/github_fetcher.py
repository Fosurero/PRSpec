"""Shared GitHub raw-file fetching with an on-disk cache.

Both :class:`~src.spec_fetcher.SpecFetcher` and
:class:`~src.code_fetcher.CodeFetcher` pull plain files from
``raw.githubusercontent.com`` and cache them locally, so the session setup,
cache lookup/write, and cache management live here once.
"""

import shutil
from pathlib import Path
from typing import List, Optional

import requests

RAW_BASE_URL = "https://raw.githubusercontent.com"


def raw_url(owner: str, repo: str, branch: str, path: str) -> str:
    """Build a raw.githubusercontent.com URL for a file in a repo."""
    return f"{RAW_BASE_URL}/{owner}/{repo}/{branch}/{path}"


class CachedGitHubFetcher:
    """Authenticated ``requests`` session plus a file-backed download cache."""

    #: Directory name used under the CWD when no *cache_dir* is supplied.
    DEFAULT_CACHE_DIRNAME = ".github_cache"

    def __init__(self, github_token: Optional[str] = None,
                 cache_dir: Optional[str] = None):
        """Set up HTTP session and local cache directory."""
        self.github_token = github_token
        self.cache_dir = (
            Path(cache_dir) if cache_dir
            else Path.cwd() / self.DEFAULT_CACHE_DIRNAME
        )
        self.session = requests.Session()

        if github_token:
            self.session.headers["Authorization"] = f"token {github_token}"

        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def fetch_cached(self, url: str, cache_key: str,
                     use_cache: bool = True) -> str:
        """Return the text at *url*, reading from / writing to the cache."""
        cache_file = self.cache_dir / cache_key

        if use_cache and cache_file.exists():
            return cache_file.read_text(encoding="utf-8")

        response = self.session.get(url)
        response.raise_for_status()

        content = response.text
        cache_file.write_text(content, encoding="utf-8")

        return content

    def fetch_raw_file(self, owner: str, repo: str, path: str,
                       branch: str, cache_key: str,
                       use_cache: bool = True) -> str:
        """Fetch a file from a GitHub repo via its raw URL."""
        return self.fetch_cached(
            raw_url(owner, repo, branch, path), cache_key, use_cache
        )

    # ---- Cache management ----

    def clear_cache(self):
        """Remove every cached file."""
        if self.cache_dir.exists():
            shutil.rmtree(self.cache_dir)
            self.cache_dir.mkdir(parents=True, exist_ok=True)

    def list_cached_files(self) -> List[str]:
        """List the names of all cached files."""
        if not self.cache_dir.exists():
            return []
        return [f.name for f in self.cache_dir.iterdir() if f.is_file()]
