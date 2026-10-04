import html
import re
from datetime import date

from bs4 import BeautifulSoup

from ..profile import TOWN_MILES

MONTHS = ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october", "november", "december"]


def clean(s: str | None) -> str:
    return re.sub(r"\s+", " ", html.unescape(s or "")).strip()


def html_to_text(fragment: str, limit: int = 6000) -> str:
    """Flatten advert HTML to readable lines (list items and paragraphs on their own line)."""
    soup = BeautifulSoup(fragment or "", "html.parser")
    for br in soup.find_all("br"):
        br.replace_with("\n")
    lines = []
    for el in soup.find_all(["p", "li", "h1", "h2", "h3", "h4", "div"]):
        if el.find(["p", "li", "div"]):
            continue
        t = clean(el.get_text(" "))
        if t:
            lines.append(t)
    text = "\n".join(lines) if lines else clean(soup.get_text("\n"))
    return text[:limit]


def parse_uk_date(text: str | None) -> str | None:
    m = re.search(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(MONTHS) + r")\s+(\d{4})\b", text or "", re.I)
    if not m:
        return None
    try:
        return date(int(m.group(3)), MONTHS.index(m.group(2).lower()) + 1, int(m.group(1))).isoformat()
    except ValueError:
        return None


def miles_for(location: str | None) -> float | None:
    """Rough straight-line miles from home using a town list. None if the town isn't known."""
    if not location:
        return None
    parts = [p.strip().lower() for p in re.split(r"[,/()]| and ", location) if p.strip()]
    for p in parts:
        p = re.sub(r"\b[a-z]{1,2}\d[a-z\d]?\s*\d[a-z]{2}\b", "", p).strip()  # drop postcodes
        if p in TOWN_MILES:
            return float(TOWN_MILES[p])
        for town, miles in TOWN_MILES.items():
            if re.search(rf"\b{re.escape(town)}\b", p):
                return float(miles)
    return None


def money(text: str) -> list[float]:
    return [float(x.replace(",", "")) for x in re.findall(r"£\s?(\d[\d,]*(?:\.\d{1,2})?)", text or "")]


def pay_from_text(text: str) -> tuple[float | None, float | None]:
    """(hourly, annual) from stated pay wording; lowest figure if a range."""
    t = text or ""
    nums = money(t)
    if not nums:
        return None, None
    low = min(nums)
    if re.search(r"per hour|an hour|/\s*h(?:ou)?r|p/?h\b|hourly", t, re.I) or low < 60:
        return (low if low < 60 else None), None
    if re.search(r"a year|per year|per annum|p\.?a\.?|annual|salary", t, re.I) or low >= 5000:
        return None, (low if low >= 5000 else None)
    return None, None
