"""Suitability score out of 100, a ranking aid, not the chance of an offer.
Method from the Codex build (SCORING.md), with fixes agreed on 4 Oct 2026:
- weights differ by lane (pay matters more for a stopgap job);
- the hours factor is no longer backwards;
- travel is estimated from distance (labelled an estimate) instead of always unknown;
- pay is compared with the roughly £12.71/hour Bailey is thought to earn now (unconfirmed).
Unknown factors count as half marks and widen the shown range."""
import re

from .profile import BANDS, ELECTRICAL_WHOLESALERS, PROFILE, WEIGHTS
from .scope import ELECTRICAL, PRACTICAL

FULL_TIME_HOURS = 37.5


def weekly_hours(text: str) -> float | None:
    m = re.search(r"(\d+(?:\.\d+)?)\s*(?:[-–to]+\s*(\d+(?:\.\d+)?)\s*)?hours?\s*(?:per|a|each|/)\s*week", text or "", re.I)
    if not m:
        return None
    return float(m.group(1))


def hourly_from(v: dict) -> tuple[float | None, str]:
    """Lowest stated hourly rate, converting an annual salary approximately if needed."""
    if v.get("pay_is_estimate"):
        return None, "estimate"
    if v.get("pay_hourly"):
        return float(v["pay_hourly"]), "stated"
    if v.get("pay_annual"):
        hrs = weekly_hours(v.get("hours_text") or "") or FULL_TIME_HOURS
        return round(float(v["pay_annual"]) / (hrs * 52), 2), "approx"
    return None, "none"


def _career(v):
    title, course = v["title"], v.get("training") or ""
    text = f"{title} {course}"
    if v["lane"] == "apprenticeship":
        cat = v.get("category")
        return {
            "Electrical": (1.0, "An electrical apprenticeship, the route you're most interested in."),
            "Engineering": (0.85, "An engineering apprenticeship, close to your electrical training."),
            "Vehicle and manufacturing": (0.6, "A practical technical apprenticeship, but further from electrical work."),
            "Construction trade": (0.55, "A construction trade apprenticeship. Practical, but further from electrical work."),
        }.get(cat, (0.3, "Not an engineering or electrical apprenticeship."))
    cat = v.get("category")
    if cat == "Electrical starter role":
        return 1.0, "Hands-on electrical work. It builds real experience towards your trade."
    if cat == "Trade counter":
        if ELECTRICAL_WHOLESALERS.search(v.get("employer", "")) or ELECTRICAL.search(text):
            return 0.85, "An electrical trade counter. You'd learn the products and meet electricians and contractors."
        return 0.6, "A trade counter job: practical products and trade customers."
    if cat == "Skilled role":
        return 0.7, "Practical, skilled work, if they'll take someone at your stage."
    if cat == "Practical starter role":
        return 0.8 if (ELECTRICAL.search(text) or PRACTICAL.search(text)) else 0.6, "A practical starter job in an engineering or technical setting."
    if cat in ("Warehouse", "Production"):
        if ELECTRICAL_WHOLESALERS.search(v.get("employer", "")):
            return 0.7, "Warehouse work at an electrical supplier: a foot in the door of the trade."
        return 0.5, f"A {cat.lower()} job. A solid stopgap, but not electrical."
    return 0.4, f"A {cat.lower() if cat else 'general'} job. A stopgap away from food service."


def _evidence(v):
    text = f"{v['title']} {v.get('training') or ''}"
    gaps = [c for c in v.get("checks", []) if c["result"] == "check" and re.search(r"experience|GCSE|qualification|certificate|Entry", c["label"])]
    if ELECTRICAL.search(text):
        return (0.65 if gaps else 0.85), "Your Level 3 Electrical Installation and college practical work fit this."
    if v["lane"] == "apprenticeship":
        return (0.55 if gaps else 0.7), "Your Level 3 college qualification and GCSEs meet typical entry requirements."
    if re.search(r"warehouse|pick|pack|stock|goods|loader|despatch|dispatch", text, re.I):
        return 0.8, "You've done warehouse work before."
    if re.search(r"production|manufactur|assembl|operative", text, re.I):
        return 0.8, "You've done production work before."
    if re.search(r"retail|customer|counter|sales|till", text, re.I):
        return 0.75, "Your customer service and till experience fit this."
    if PRACTICAL.search(text):
        return 0.7, "Your practical college training is relevant."
    return None, "Hard to tell how well your experience fits."


def _travel(v):
    d = v.get("distance_miles")
    loc = v.get("location") or "the location"
    if re.search(r"seagoing|\bat sea\b|offshore|\bvessels?\b|\bships?\b|submarin|royal navy", f"{v['title']} {v.get('text','')[:1500]}", re.I):
        return (0.55 if PROFILE["seagoing"] else 0.1), "Involves time at sea. You said you'd consider that."
    if d is None:
        return None, f"Distance from home not known ({loc}). Check the journey."
    if d <= 6:
        return 0.9, f"About {d:g} mile{'' if d == 1 else 's'} from home. Likely doable by bus or a lift; check the route."
    if d <= 12:
        return 0.65, f"About {d:g} miles from home. Might be within 30 minutes without driving yourself; check the route and shift times."
    if d <= 20:
        return 0.35, f"About {d:g} miles from home. Probably over 30 minutes unless someone drives you."
    if v["lane"] == "apprenticeship" and d <= 40:
        return (0.3 if PROFILE["relocation"] else 0.05), f"About {d:g} miles away. Too far to travel daily without driving; it would probably mean moving, which you said you'd consider for the right apprenticeship."
    if v["lane"] == "apprenticeship":
        return (0.15 if PROFILE["relocation"] else 0.0), f"About {d:g} miles away. You'd need to move or travel a long way; you said you'd consider moving for the right apprenticeship."
    return 0.1, f"About {d:g} miles away. Too far for a stopgap job."


def _hours(v):
    t = f"{v.get('hours_text') or ''} {v.get('contract') or ''}"
    hrs = weekly_hours(t)
    if hrs is not None:
        if hrs >= 30:
            return 1.0, f"{hrs:g} hours a week: full-time, which is what you want."
        return 0.45, f"Only {hrs:g} hours a week. You'd prefer full-time."
    if re.search(r"full[ -]?time", t, re.I) and not re.search(r"part[ -]?time", t, re.I):
        return 1.0, "Full-time, which is what you want."
    if re.search(r"part[ -]?time", t, re.I) and not re.search(r"full[ -]?time", t, re.I):
        return 0.45, "Part-time. You'd prefer full-time."
    if re.search(r"temporary|temp\b|seasonal|fixed[ -]term", t, re.I):
        return 0.5, "Temporary or fixed-term work."
    return None, "Hours not stated."


def _shifts(v):
    t = f"{v.get('pattern_text') or ''} {v.get('hours_text') or ''} {(v.get('text') or '')[:3000]}"
    if not t.strip():
        return None, "Shift pattern not stated."
    nights = re.search(r"\bnights?\b|night shift|\b(?:22|23|00|01|02|03|04):\d\d|10\s*pm|11\s*pm", t, re.I) and not re.search(r"no nights?", t, re.I)
    weekends = re.search(r"weekend|saturday|sunday|\d\s*on\s*\d\s*off|4 on|continental", t, re.I)
    rotating = re.search(r"rotat|continental|varied shifts|different shifts|flexible shifts", t, re.I)
    days = re.search(r"monday\s*(?:to|-|–)\s*friday|mon\s*(?:to|-|–)\s*fri|weekdays|days only|day shift|days\b", t, re.I)
    if nights:
        return 0.2, "Involves night shifts. You'd prefer days."
    if rotating:
        return 0.55, "Rotating or varied shifts, so less routine."
    if weekends and not days:
        return 0.45, "Includes weekend work."
    if days and weekends:
        return 0.7, "Mostly weekdays, with some weekends."
    if days:
        return 1.0, "Weekday daytime hours."
    return None, "Shift pattern not stated."


def _pay(v):
    hourly, how = hourly_from(v)
    if hourly is None:
        return None, "Pay not stated." if how != "estimate" else "Pay shown is only an estimate."
    cur = PROFILE["current_hourly"]
    approx = "about " if how == "approx" else ""
    if v["lane"] == "apprenticeship":
        annual = v.get("pay_annual") or hourly * FULL_TIME_HOURS * 52
        if annual >= 20000:
            return 1.0, f"Pay is {approx}£{hourly:.2f} an hour, good for an apprenticeship."
        if annual >= 15000:
            return 0.7, f"Pay is {approx}£{hourly:.2f} an hour, typical for an apprenticeship."
        return 0.45, f"Pay is {approx}£{hourly:.2f} an hour, at the low end, but the training is what counts."
    diff = hourly - cur
    if diff >= 1.25:
        return 1.0, f"Pay is {approx}£{hourly:.2f} an hour, well above the roughly £{cur:.2f} you get now."
    if diff >= 0.4:
        return 0.75, f"Pay is {approx}£{hourly:.2f} an hour, a bit above the roughly £{cur:.2f} you get now."
    if diff >= -0.05:
        return 0.45, f"Pay is {approx}£{hourly:.2f} an hour, about the same as now."
    return 0.15, f"Pay is {approx}£{hourly:.2f} an hour, less than the roughly £{cur:.2f} you get now."


def _workplace(v):
    t = (v.get("text") or "")[:4000]
    if re.search(r"noisy|high noise|hearing protection|ear defenders|loud environment", t, re.I) and not re.search(r"\bnot noisy\b", t, re.I):
        return 0.25, "The advert mentions a noisy environment."
    if re.search(r"full training|structured training|induction|mentor|buddy|clear (?:instructions|procedures)|supervis|we will train|training provided", t, re.I):
        return 0.85, "The advert mentions training or support when you start."
    return None, None


FACTORS = {"career": _career, "evidence": _evidence, "travel": _travel, "hours": _hours, "shifts": _shifts, "pay": _pay, "workplace": _workplace}
LABELS = {"career": "Career fit", "evidence": "Your experience", "travel": "Travel", "hours": "Hours", "shifts": "Shifts", "pay": "Pay", "workplace": "Workplace"}


def score(v: dict) -> dict:
    weights = WEIGHTS[v["lane"]]
    factors, known, unknown = [], 0.0, 0.0
    for key, w in weights.items():
        value, note = FACTORS[key](v)
        if value is None:
            unknown += w
        else:
            known += w * value
        factors.append({"key": key, "label": LABELS[key], "weight": w, "value": value,
                        "points": None if value is None else round(w * value, 1), "note": note})
    total = round(known + 0.5 * unknown)
    travel = next(f for f in factors if f["key"] == "travel")
    if travel["value"] is not None and travel["value"] < 0.35 and total >= 75:
        total = 74  # a strong match has to be realistic to get to (or a seagoing role he'd consider)
        factors.append({"key": "cap", "label": "Distance cap", "weight": 0, "value": None, "points": None,
                        "note": "Held below Strong because of the distance from home."})
    band = next(name for floor, name in BANDS if total >= floor)
    why = [f["note"] for f in sorted(factors, key=lambda f: -(f["points"] or 0)) if f["value"] is not None and f["value"] >= 0.75 and f["note"]][:3]
    gaps = [ch["note"] for ch in v.get("checks", []) if ch["result"] != "met"]
    gaps += [f["note"] for f in factors if f["note"] and (f["value"] is None or f["value"] < 0.5) and f["key"] != "workplace"]
    return {"score": total, "score_low": round(known), "score_high": round(known + unknown), "band": band,
            "factors": factors, "why": why, "gaps": gaps[:5]}
