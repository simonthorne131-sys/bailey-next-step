"""GOV.UK Find an Apprenticeship: ordinary public search and advert pages (no key needed).
Checked 4 Oct 2026: the site's terms don't restrict reading pages; robots.txt isn't served.
Route codes from the search form: 5 = Construction and building, 9 = Engineering and
manufacturing (7 = Digital is left out: IT roles are excluded from Bailey's search)."""
import re
from urllib.parse import urlencode, urljoin, urlparse

from bs4 import BeautifulSoup

from .. import net
from .common import clean, parse_uk_date, pay_from_text

NAME = "GOV.UK Find an apprenticeship"
ORIGIN = "https://www.findapprenticeship.service.gov.uk"

# (description, query, max pages, stop once results are further than this many miles)
SEARCHES = [
    ("Construction and engineering near Milton Keynes",
     {"location": "Milton Keynes", "distance": "all", "sort": "DistanceAsc", "routeIds": ["5", "9"]}, 12, 30),
    ("Electrical anywhere in England",
     {"searchTerm": "electrical", "location": "Milton Keynes", "distance": "all", "sort": "DistanceAsc"}, 4, None),
    ("Marine and seagoing",
     {"searchTerm": "marine", "location": "Milton Keynes", "distance": "all", "sort": "DistanceAsc"}, 2, None),
    ("Wind and renewables",
     {"searchTerm": "wind turbine", "location": "Milton Keynes", "distance": "all", "sort": "DistanceAsc"}, 2, None),
]


def search_url(query: dict) -> str:
    pairs = []
    for k, v in query.items():
        for item in (v if isinstance(v, list) else [v]):
            pairs.append((k, item))
    return f"{ORIGIN}/apprenticeships?{urlencode(pairs)}"


def parse_search(html: str, page_url: str) -> tuple[list[dict], int, str | None]:
    soup = BeautifulSoup(html, "html.parser")
    heading = clean(soup.h1.get_text(" ") if soup.h1 else "")
    m = re.search(r"([\d,]+) results? found", heading)
    if not m:
        if re.search(r"no (?:apprenticeships|results)", heading, re.I):
            return [], 0, None
        raise net.FetchError("GOV.UK search page didn't have its usual results heading")
    total = int(m.group(1).replace(",", ""))
    cards = soup.select("li.das-search-results__list-item")
    if total and not cards:
        raise net.FetchError("GOV.UK reported results but none could be read")
    out = []
    for li in cards:
        a = li.select_one("h2 a")
        if not a or not a.get("href"):
            continue
        url = urljoin(ORIGIN, a["href"])
        title = re.sub(r"\s*\(opens in new tab\)$", "", clean(a.get_text(" ")))
        ps = [clean(p.get_text(" ")) for p in li.select(".faa-search_results__content > p")]
        if len(ps) < 2:
            continue
        employer, location = ps[0], ps[1]
        fields = {}
        for p in ps[2:]:
            for label in ("Distance", "Wage", "Training course", "Start date", "Closes", "Apply on"):
                if p.startswith(label):
                    fields[label] = p[len(label):].strip()
        dist = re.search(r"([\d.]+) miles", fields.get("Distance", ""))
        on_gov = urlparse(url).netloc == urlparse(ORIGIN).netloc
        hourly, annual = pay_from_text(fields.get("Wage", ""))
        course = fields.get("Training course", "")
        level = re.search(r"level (\d)", course, re.I)
        out.append({
            "id": "faa:" + (urlparse(url).path.rsplit("/", 1)[-1] if on_gov else url),
            "source": NAME, "lane": "apprenticeship", "title": title, "employer": employer,
            "location": location, "distance_miles": float(dist.group(1)) if dist else None,
            "pay_text": fields.get("Wage") or None, "pay_hourly": hourly, "pay_annual": annual,
            "training": course or None, "level": int(level.group(1)) if level else None,
            "start_date": parse_uk_date(fields.get("Start date")),
            "closes": parse_uk_date(fields.get("Closes")) or (None if "Closes" not in fields else None),
            "url": url, "apply_route": "Apply through GOV.UK (you'll need a free account)" if on_gov else f"Apply on {urlparse(url).netloc}",
            "checkable": on_gov,
        })
    nxt = soup.select_one("a[rel=next]")
    return out, total, (urljoin(page_url, nxt["href"]) if nxt and nxt.get("href") else None)


def parse_detail(html: str, v: dict) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    heading = clean(soup.h1.get_text(" ") if soup.h1 else "")
    main = clean(soup.main.get_text(" ") if soup.main else soup.get_text(" "))
    if heading == "Page not found" or re.search(r"You can no longer apply|This apprenticeship (?:has )?closed|vacancy has closed", f"{heading} {main}", re.I):
        return {**v, "live": "closed", "live_note": "GOV.UK says this advert has closed."}
    if not soup.select_one("#summary") or not soup.select_one("#requirements"):
        raise net.FetchError("GOV.UK advert page wasn't in its usual layout")
    rows = {}
    for r in soup.select("#summary .govuk-summary-list__row"):
        if r.dt and r.dd:
            rows[clean(r.dt.get_text(" "))] = clean(r.dd.get_text(" "))
    wage = re.sub(r"\s*Minimum wage rates.*$", "", rows.get("Wage", "")) or v.get("pay_text")
    hourly, annual = pay_from_text(wage or "")
    req = soup.select_one("#requirements")
    for h in req.find_all(["h3", "h4"]):
        h.insert_after(": ")
        h.insert_before("\n")
    for li in req.find_all("li"):
        li.insert_after("\n")
    req_text = re.sub(r"[ \t]+", " ", req.get_text(" ")).replace("Requirements", "", 1).strip()
    work = soup.select_one("#work")
    training = soup.select_one("#training")
    closing = soup.select_one(".faa-vacancy__closing-date")
    loc = soup.select_one("[itemprop=jobLocation]")
    return {
        **v,
        "pay_text": wage or None, "pay_hourly": hourly, "pay_annual": annual,
        "hours_text": rows.get("Hours") or None,
        "pattern_text": rows.get("Hours") or None,
        "training": rows.get("Training course") or v.get("training"),
        "duration": rows.get("Duration") or None,
        "start_date": parse_uk_date(rows.get("Start date")) or v.get("start_date"),
        "closes": parse_uk_date(closing.get_text(" ") if closing else "") or v.get("closes"),
        "location": clean(loc.get_text(" "))[:160] if loc else v["location"],
        "requirements": req_text[:4000],
        "text": "\n".join(x for x in [req_text[:4000], clean(work.get_text(" "))[:3000] if work else "", clean(training.get_text(" "))[:1000] if training else ""] if x),
        "live": "open", "live_note": "Checked on GOV.UK.",
        "detail_checked": True,
    }


def fetch_all(log) -> list[dict]:
    seen, out = set(), []
    for label, query, max_pages, max_miles in SEARCHES:
        url, pages = search_url(query), 0
        while url and pages < max_pages:
            html, _ = net.fetch(url)
            items, total, url = parse_search(html, url)
            pages += 1
            for it in items:
                if it["id"] not in seen:
                    seen.add(it["id"])
                    out.append(it)
            if max_miles and items and all((i["distance_miles"] or 0) > max_miles for i in items[-3:]):
                break
        log(f"{label}: {pages} page(s) read")
    return out


def recheck(v: dict) -> dict:
    """Fetch the full advert. Raises net.Gone if the page has gone."""
    html, _ = net.fetch(v["url"])
    return parse_detail(html, v)
