"""Polite HTTP for the weekly run: one request at a time, a pause between requests,
a clear user agent, and no retries that could look like hammering a site."""
import json
import re
import time
import urllib.error
import urllib.request

USER_AGENT = "Mozilla/5.0 (compatible; BaileyNextStep/1.0; weekly personal job search)"
PAUSE_SECONDS = 1.5
MAX_BYTES = 3_000_000

_last_call = 0.0


class FetchError(Exception):
    """The source could not be read. Never treat this as 'no vacancies' or 'closed'."""


class Gone(Exception):
    """The source answered that the page no longer exists (404/410)."""


def fetch(url: str, accept: str = "text/html") -> tuple[str, dict]:
    global _last_call
    wait = PAUSE_SECONDS - (time.monotonic() - _last_call)
    if wait > 0:
        time.sleep(wait)
    _last_call = time.monotonic()
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": accept})
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = resp.read(MAX_BYTES + 1)
            if len(body) > MAX_BYTES:
                raise FetchError(f"Page too large: {url}")
            headers = {k.lower(): v for k, v in resp.headers.items()}
            return body.decode("utf-8", errors="replace"), headers
    except urllib.error.HTTPError as e:
        if e.code in (404, 410):
            raise Gone(f"HTTP {e.code}") from e
        raise FetchError(f"HTTP {e.code} from {url}") from e
    except (urllib.error.URLError, TimeoutError, ConnectionError) as e:
        raise FetchError(f"Could not reach {url}: {e}") from e


def fetch_json(url: str):
    text, headers = fetch(url, accept="application/json")
    return json.loads(text), headers


def next_data(html: str) -> dict:
    """Read the JSON a Next.js page embeds for itself (used by Reed)."""
    m = re.search(r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', html, re.S)
    if not m:
        raise FetchError("Page did not contain its expected data block")
    return json.loads(m.group(1))
