"""Reed.co.uk public search and job pages, read from the data each page embeds.
Checked 4 Oct 2026: robots.txt allows /jobs/ pages (it only disallows sortBy and some
internal paths, which this reader never uses). One page per search, a pause between requests.
Expired adverts answer HTTP 410."""
import re

from .. import net
from .common import clean, html_to_text, miles_for, parse_uk_date

NAME = "Reed"
ORIGIN = "https://www.reed.co.uk"

JOB_SEARCHES = [
    "electricians-mate", "electrical-labourer", "trainee-electrician", "electrical-assistant",
    "maintenance-assistant", "trainee-engineer", "engineering-operative", "trainee-technician",
    "trade-counter", "electrical-wholesale", "warehouse-operative", "production-operative",
    "retail-assistant", "admin-assistant", "site-operative", "labourer",
]
APPRENTICESHIP_SEARCHES = ["electrical-apprentice", "engineering-apprentice", "maintenance-apprentice", "apprentice-electrician"]
PROXIMITY = 15

SALARY_UNITS = {1: "per hour", 2: "per day", 3: "per week", 4: "per month", 5: "per year"}
CONTRACT = {1: "Permanent", 2: "Contract", 4: "Temporary"}


def search_url(slug: str) -> str:
    return f"{ORIGIN}/jobs/{slug}-jobs-in-milton-keynes?proximity={PROXIMITY}"


def from_listing(j: dict) -> dict:
    d = j["jobDetail"]
    unit = d.get("salaryType")
    lo, hi = d.get("salaryFrom") or 0, d.get("salaryTo") or 0
    pay_text, hourly, annual = None, None, None
    if lo:
        rng = f"£{lo:,.2f}" if lo < 100 else f"£{lo:,.0f}"
        if hi and hi != lo:
            rng += f" to £{hi:,.2f}" if hi < 100 else f" to £{hi:,.0f}"
        pay_text = f"{rng} {SALARY_UNITS.get(unit, '')}".strip()
        if unit == 1:
            hourly = float(lo)
        elif unit == 5:
            annual = float(lo)
    title = clean(d["jobTitle"])
    hours = "Full-time" if d.get("isFullTime") and not d.get("isPartTime") else (
        "Part-time" if d.get("isPartTime") and not d.get("isFullTime") else ("Full-time or part-time" if d.get("isFullTime") else None))
    location = clean(d.get("displayLocationName"))
    return {
        "id": f"reed:{d['jobId']}", "source": NAME,
        "lane": "apprenticeship" if re.search(r"apprentic", title, re.I) else "job",
        "title": title, "employer": clean(j.get("profileName") or d.get("ouName")),
        "location": location, "distance_miles": miles_for(location),
        "pay_text": pay_text, "pay_hourly": hourly, "pay_annual": annual,
        "hours_text": hours, "contract": CONTRACT.get(d.get("jobType")),
        "posted": (d.get("displayDate") or "")[:10] or None,
        "listing_ends": (d.get("expiryDate") or "")[:10] or None,
        "url": ORIGIN + j["url"], "apply_route": "Apply on Reed (free account) or the employer's site",
        "text": clean(d.get("jobDescriptionSnippet")), "checkable": True,
        "is_training_course": bool(d.get("isTrainingJob")),
    }


def parse_search(html: str) -> list[dict]:
    data = net.next_data(html)
    sr = data["props"]["pageProps"]["searchResults"]
    return [from_listing(j) for j in sr.get("jobs", []) if j.get("jobDetail")]


def parse_detail(html: str, v: dict) -> dict:
    data = net.next_data(html)
    jd = data["props"]["pageProps"]["consolidatedJobDetails"]["jobDetails"]
    if not jd.get("isLive", True) or jd.get("isSuspended"):
        return {**v, "live": "closed", "live_note": "Reed says this job is no longer live."}
    text = html_to_text(jd.get("description", ""))
    loc = jd.get("jobLocation") or {}
    town = clean(loc.get("townName") or loc.get("locationName"))
    contract = (jd.get("jobContractType") or {}).get("name") or v.get("contract")
    closes = None
    m = re.search(r"closing date\s*:?\s*([^\n]{0,40})", text, re.I)
    if m:
        closes = parse_uk_date(m.group(1))
    pattern = "\n".join(l for l in text.split("\n") if re.search(
        r"monday|tuesday|wednesday|thursday|friday|saturday|sunday|weekend|shift|\d{1,2}(?::\d\d)?\s*(?:am|pm)|\d\d:\d\d|rotat|on\s*\d\s*off", l, re.I))[:600]
    return {
        **v, "text": text, "requirements": None, "contract": contract,
        "location": town or v["location"], "distance_miles": miles_for(town) or v.get("distance_miles"),
        "pattern_text": pattern or None, "closes": closes or v.get("closes"),
        "live": "open", "live_note": "Checked on Reed.", "detail_checked": True,
    }


def fetch_all(log) -> list[dict]:
    seen, out = set(), []
    for slug in JOB_SEARCHES + APPRENTICESHIP_SEARCHES:
        html, _ = net.fetch(search_url(slug))
        items = parse_search(html)
        new = [i for i in items if i["id"] not in seen and not i["is_training_course"]]
        for i in new:
            seen.add(i["id"])
        out += new
    log(f"{len(JOB_SEARCHES) + len(APPRENTICESHIP_SEARCHES)} searches read")
    return out


def recheck(v: dict) -> dict:
    html, _ = net.fetch(v["url"])
    return parse_detail(html, v)
