from __future__ import annotations

from urllib.request import Request, urlopen

from . import __version__
from .config import SourceConfig


USER_AGENT = f"CourseMesh/{__version__}"
MAX_FEED_BYTES = 10 * 1024 * 1024


def fetch_source(source: SourceConfig, timeout: float = 15.0) -> str:
    if source.path:
        if source.path.stat().st_size > MAX_FEED_BYTES:
            raise ValueError("Calendar feed exceeds the 10 MiB safety limit")
        return source.path.read_text(encoding="utf-8")

    url = source.resolved_url()
    if not url:
        raise ValueError(f"Source {source.id!r} does not resolve to a URL")
    if not url.lower().startswith(("https://", "http://")):
        raise ValueError("Only http:// and https:// calendar URLs are supported")

    request = Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/calendar,*/*;q=0.1"},
    )
    with urlopen(request, timeout=timeout) as response:
        body = response.read(MAX_FEED_BYTES + 1)
        if len(body) > MAX_FEED_BYTES:
            raise ValueError("Calendar feed exceeds the 10 MiB safety limit")
        charset = response.headers.get_content_charset() or "utf-8"
        return body.decode(charset)
