from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from . import __version__
from .config import SourceConfig
from .models import HttpCacheState


USER_AGENT = f"CourseMesh/{__version__}"
MAX_FEED_BYTES = 10 * 1024 * 1024
MAX_VALIDATOR_BYTES = 4096


@dataclass(frozen=True)
class FetchResult:
    text: str | None
    http_cache: HttpCacheState | None = None
    not_modified: bool = False


def fetch_source(
    source: SourceConfig,
    timeout: float = 15.0,
    *,
    http_cache: HttpCacheState | None = None,
) -> FetchResult:
    if source.path:
        if source.path.stat().st_size > MAX_FEED_BYTES:
            raise ValueError("Calendar feed exceeds the 10 MiB safety limit")
        return FetchResult(source.path.read_text(encoding="utf-8"))

    url = source.resolved_url()
    if not url:
        raise ValueError(f"Source {source.id!r} does not resolve to a URL")
    if not url.lower().startswith(("https://", "http://")):
        raise ValueError("Only http:// and https:// calendar URLs are supported")

    resource_key = _resource_key(url)
    active_cache = (
        http_cache if http_cache and http_cache.resource_key == resource_key else None
    )
    headers = {"User-Agent": USER_AGENT, "Accept": "text/calendar,*/*;q=0.1"}
    if active_cache:
        etag = _safe_validator(active_cache.etag)
        last_modified = _safe_validator(active_cache.last_modified)
        if etag:
            headers["If-None-Match"] = etag
        if last_modified:
            headers["If-Modified-Since"] = last_modified

    request = Request(url, headers=headers)
    sent_conditional = "If-None-Match" in headers or "If-Modified-Since" in headers
    try:
        with urlopen(request, timeout=timeout) as response:
            body = response.read(MAX_FEED_BYTES + 1)
            if len(body) > MAX_FEED_BYTES:
                raise ValueError("Calendar feed exceeds the 10 MiB safety limit")
            charset = response.headers.get_content_charset() or "utf-8"
            return FetchResult(
                body.decode(charset),
                _response_cache(resource_key, response.headers),
            )
    except HTTPError as exc:
        if exc.code != 304:
            raise
        if not sent_conditional or active_cache is None:
            raise ValueError(
                "Provider returned HTTP 304 without a matching conditional request"
            ) from exc
        return FetchResult(
            None,
            HttpCacheState(
                resource_key=resource_key,
                etag=_header_validator(exc.headers, "ETag") or active_cache.etag,
                last_modified=(
                    _header_validator(exc.headers, "Last-Modified")
                    or active_cache.last_modified
                ),
            ),
            not_modified=True,
        )


def _resource_key(url: str) -> str:
    return sha256(url.encode("utf-8")).hexdigest()


def _response_cache(resource_key: str, headers) -> HttpCacheState | None:
    etag = _header_validator(headers, "ETag")
    last_modified = _header_validator(headers, "Last-Modified")
    if etag is None and last_modified is None:
        return None
    return HttpCacheState(
        resource_key=resource_key,
        etag=etag,
        last_modified=last_modified,
    )


def _header_validator(headers, name: str) -> str | None:
    if headers is None:
        return None
    return _safe_validator(headers.get(name))


def _safe_validator(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not value or "\r" in value or "\n" in value:
        return None
    if len(value.encode("utf-8")) > MAX_VALIDATOR_BYTES:
        return None
    return value
