"""Two Milton Keynes recruitment agencies that publish vacancies through the standard
WordPress job-listings feed (no key). Checked by the Codex build on 27 Sep 2026: robots.txt
doesn't restrict these feeds and the agencies' terms don't restrict reading vacancies."""
import re

from .. import net
from .common import clean, html_to_text, miles_for, pay_from_text

AGENCIES = [
    {"key": "rapier", "name": "Rapier Employment",
     "api": "https://rapieremployment.co.uk/wp-json/wp/v2/job-listings", "query": "&search=Milton+Keynes"},
    {"key": "insight", "name": "Insight Employment",
     "api": "https://insightemployment.co.uk/dir/wp-json/wp/v2/job-listings", "query": ""},
]
PAY_LINE = re.compile(r"£.*(?:hour|p/?h|per annum|per year|salary|pay|shift)", re.I)


def from_record(r: dict, agency: dict) -> dict:
    meta = r.get("meta") or {}
    text = html_to_text((r.get("content") or {}).get("rendered", ""))
    pay_lines = [l for l in text.split("\n") if PAY_LINE.search(l) and not re.search(r"pension|holiday|gym|discount", l, re.I)]
    pay_text = clean(meta.get("_job_salary")) or (" | ".join(pay_lines)[:200] or None)
    hourly, annual = pay_from_text(pay_text or "")
    hours = re.search(r"\d+\s*(?:[–-]\s*\d+\s*)?hours? (?:per|a|each) week", text, re.I)
    pattern = "\n".join(l for l in text.split("\n") if re.search(
        r"monday|friday|saturday|sunday|weekend|shift|\d{1,2}(?::\d\d)?\s*(?:am|pm)|\d\d[:.]\d\d|rotat|on\s*\d\s*off|continental", l, re.I))[:600]
    application = clean(meta.get("_application"))
    location = clean(meta.get("_job_location"))
    filled = str(meta.get("_filled", "0")).lower() in ("1", "true")
    title = clean(r["title"]["rendered"])
    return {
        "id": f"{agency['key']}:{r['id']}", "source": agency["name"], "lane": "apprenticeship" if re.search(r"apprentic", title, re.I) else "job",
        "title": title, "employer": clean(meta.get("_company_name")) or f"{agency['name']} (agency; employer not named)",
        "location": location, "distance_miles": miles_for(location),
        "pay_text": pay_text, "pay_hourly": hourly, "pay_annual": annual,
        "hours_text": hours.group(0) if hours else ("Full-time" if re.search(r"full[ -]time", text, re.I) else None),
        "pattern_text": pattern or None, "posted": (r.get("date") or "")[:10] or None,
        "url": r["link"], "apply_route": "Apply by email (address on the agency advert)" if "@" in application else f"Apply via the agency's link",
        "text": text, "requirements": None, "checkable": True, "api_item": f"{agency['api']}/{r['id']}",
        "live": "closed" if filled else "open", "live_note": "The agency marks this job as filled." if filled else f"Listed by {agency['name']}.",
        "detail_checked": True,
    }


def fetch_agency(a: dict, log) -> list[dict]:
    out, page, pages = [], 1, 1
    while page <= pages:
        data, headers = net.fetch_json(f"{a['api']}?per_page=50&page={page}{a['query']}")
        if "x-wp-totalpages" not in headers:
            raise net.FetchError(f"{a['name']} feed didn't say how many pages it has")
        pages = min(int(headers["x-wp-totalpages"]), 4)
        out += [from_record(r, a) for r in data if r.get("status") == "publish"]
        page += 1
    log(f"{a['name']}: {len(out)} listed")
    return out


def recheck(v: dict) -> dict:
    agency = next(a for a in AGENCIES if v["id"].startswith(a["key"] + ":"))
    data, _ = net.fetch_json(v["api_item"])  # raises net.Gone if removed
    return from_record(data, agency)
