"""Weekly run: fetch → scope → full advert check → liveness of older adverts → dedupe →
requirement checks → score → write data/vacancies.json and data/run.json.

Rules carried over from the brief:
- Never invent pay, dates or requirements: unknowns stay empty and show as "not stated".
- A source that fails is reported as failed. It never looks like "no vacancies", and its
  older adverts are kept as "not re-checked" rather than closed.
- An advert is only marked closed when the source says so, it has gone (404/410), or its
  stated closing date has passed.
Usage: python -m scout.run [--dry-run]"""
import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from . import net
from .checks import blocked, requirement_checks
from .profile import PROFILE
from .scope import apprenticeship_category, career_excluded, job_category
from .scoring import hourly_from, score
from .sources import faa, reed, wpjobs

DATA = Path(__file__).resolve().parent.parent / "data"
UK = ZoneInfo("Europe/London")
KEEP_CLOSED_DAYS = 21
MAX_DETAIL_CHECKS = {"faa": 160, "reed": 160}
FAR_FOR_A_JOB = 25

SOURCES = [
    ("faa", faa.NAME, faa.fetch_all, faa.recheck),
    ("reed", reed.NAME, reed.fetch_all, reed.recheck),
    ("rapier", "Rapier Employment", lambda log: wpjobs.fetch_agency(wpjobs.AGENCIES[0], log), wpjobs.recheck),
    ("insight", "Insight Employment", lambda log: wpjobs.fetch_agency(wpjobs.AGENCIES[1], log), wpjobs.recheck),
]


def source_key(vid: str) -> str:
    return vid.split(":", 1)[0]


def norm(s: str | None) -> str:
    s = (s or "").lower()
    s = re.sub(r"\b(?:ltd|limited|plc|llp|uk|group|the)\b|&amp;|[^a-z0-9 ]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def dedupe_key(v: dict) -> str:
    """Same employer and same role = one card, even if advertised at several branches."""
    words = norm(v["title"]).split()[:5]
    return f"{norm(v['employer'])}|{' '.join(words)}"


def classify(v: dict) -> dict:
    """Decide lane category, or mark as out of scope. Returns the vacancy with fields set."""
    reason = career_excluded(v["title"], v.get("training") or "")
    if v["lane"] == "apprenticeship":
        v["category"] = apprenticeship_category(v["title"], v.get("training") or "")
        if not reason and v["category"] == "Other":
            reason = "Not a practical or engineering apprenticeship"
    else:
        v["category"] = job_category(v["title"])
        if not reason and not v["category"]:
            reason = "Not one of the job types in your search"
        if not reason and v.get("distance_miles") and v["distance_miles"] > FAR_FOR_A_JOB:
            reason = "Too far away for a stopgap job"
    v["out_of_scope"] = reason
    return v


def apply_closing_date(v: dict, today: str) -> dict:
    if v.get("live") != "closed" and v.get("closes") and v["closes"] < today:
        v["live"], v["live_note"] = "closed", f"Closing date ({v['closes']}) has passed."
    return v


def run(dry_run: bool = False, today: date | None = None, fetchers=None) -> dict:
    now = datetime.now(UK)
    today_s = (today or now.date()).isoformat()
    log_lines: list[str] = []

    def log(msg):
        log_lines.append(msg)
        print(msg, flush=True)

    old_doc = load_json(DATA / "vacancies.json", {"items": []})
    old = {v["id"]: v for v in old_doc.get("items", [])}

    sources = fetchers or SOURCES
    report, fresh, failed = [], {}, set()
    for key, name, fetch_all, _ in sources:
        try:
            items = fetch_all(log)
            for it in items:
                fresh.setdefault(it["id"], it)
            report.append({"key": key, "name": name, "ok": True, "listed": len(items), "note": ""})
        except Exception as e:  # report every failure honestly; keep going with other sources
            failed.add(key)
            report.append({"key": key, "name": name, "ok": False, "listed": 0, "note": str(e)[:200]})
            log(f"{name}: FAILED: {e}")

    rechecker = {k: r for k, _, _, r in sources}
    detail_budget = dict(MAX_DETAIL_CHECKS)
    result: dict[str, dict] = {}

    # 1. This week's listings: classify, then read the full advert for those in scope.
    for vid, v in fresh.items():
        v = classify({**old.get(vid, {}), **v, "detail_checked": v.get("detail_checked", False)})
        if v["out_of_scope"]:
            continue
        sk = source_key(vid)
        if v.get("checkable") and not v.get("detail_checked") and v.get("live") != "closed":
            if detail_budget.get(sk, 999) > 0:
                detail_budget[sk] = detail_budget.get(sk, 999) - 1
                v = check_one(v, rechecker[sk], log)
            else:
                v.update(live="open", live_note="Listed this week; full advert not read yet.")
        v.setdefault("live", "open")
        v = classify(v)  # title or course may be more precise after the full read
        if v["out_of_scope"]:
            continue
        result[vid] = v

    # 2. Older adverts that weren't in this week's listings: re-check them directly.
    for vid, v in old.items():
        if vid in result:
            continue
        v = classify(dict(v))  # rules may have changed since last week
        if v["out_of_scope"]:
            continue
        sk = source_key(vid)
        if v.get("live") == "closed":
            result[vid] = v
            continue
        if sk in failed or sk not in rechecker:
            v.update(live="unverified", live_note="Couldn't re-check this week (the source didn't respond).")
        elif v.get("checkable"):
            v = check_one(v, rechecker[sk], log)
        else:
            v.update(live="unverified", live_note="No longer in the search results and can't be re-checked. It may have closed.")
        result[vid] = v

    # 3. Closing dates, dedupe, checks, scores, dates seen.
    merged: dict[str, dict] = {}
    for v in result.values():
        v = apply_closing_date(v, today_s)
        v["first_seen"] = old.get(v["id"], {}).get("first_seen") or today_s
        v["last_checked"] = today_s
        v["is_new"] = v["id"] not in old
        k = dedupe_key(v)
        if k in merged:
            keep, other = merged[k], v
            if (v.get("distance_miles") or 999) < (keep.get("distance_miles") or 999) and v["live"] != "closed":
                keep, other = v, keep  # show the nearest branch
            links = set(keep.get("other_links", [])) | set(other.get("other_links", [])) | {other["url"]}
            keep["other_links"] = sorted(links - {keep["url"]})
            if norm(other.get("location")) != norm(keep.get("location")):
                keep["other_locations"] = sorted(set(keep.get("other_locations", [])) | {other.get("location") or ""} - {""})
            keep["is_new"] = keep["is_new"] and other["is_new"]
            merged[k] = keep
            continue
        merged[k] = v

    items = []
    for v in merged.values():
        if v["live"] == "closed" and v.get("closed_on") and v["closed_on"] < (date.fromisoformat(today_s) - timedelta(days=KEEP_CLOSED_DAYS)).isoformat():
            continue
        if v["live"] == "closed":
            v.setdefault("closed_on", today_s)
        hourly, _ = hourly_from(v)
        v["checks"] = requirement_checks(v["title"], v.get("text") or "", PROFILE, v["lane"], starter_pay=hourly is not None and hourly <= 15.5)
        for field in ("hours_text", "pattern_text", "pay_text"):
            if v.get(field) and re.search(r"click apply|see (?:the )?full details|to be confirmed|discussed at interview", v[field], re.I):
                v[field] = None
        if v.get("pay_text"):
            v["pay_text"] = re.sub(r"^(\w+)\s+\1\b", r"\1", v["pay_text"])
        annual = v.get("pay_annual") or (hourly * 37.5 * 52 if hourly else None)
        if v["lane"] == "job" and annual and annual >= 33000 and v.get("category") in ("Practical starter role", "Electrical starter role"):
            v["checks"].append({"label": "Experience level", "result": "check",
                                "note": "The pay is high for a starter job, which usually means they want some experience. Read the requirements."})
        v["blocked"] = blocked(v["checks"])
        v.update(score(v))
        v.pop("checkable_reason", None)
        items.append(v)

    def travel_points(v):
        return next((f["value"] or 0 for f in v.get("factors", []) if f["key"] == "travel"), 0)
    items.sort(key=lambda v: (v["live"] == "closed", v["blocked"], -v["score"], -travel_points(v), v["title"]))
    items = fold_big_employers(items)
    summary = summarise(items, report, today_s)
    run_doc = {"run_at": now.isoformat(timespec="minutes"), "today": today_s, "sources": report, "summary": summary,
               "log": log_lines[-60:]}
    if not dry_run:
        DATA.mkdir(exist_ok=True)
        write_json(DATA / "vacancies.json", {"generated": now.isoformat(timespec="minutes"), "items": items})
        write_json(DATA / "run.json", run_doc)
    log(json.dumps(summary))
    return {"items": items, "run": run_doc}


MAX_CARDS_PER_EMPLOYER = 2


def fold_big_employers(items: list[dict]) -> list[dict]:
    """Show at most two active cards per employer per lane; link the rest from the top card."""
    shown: dict[tuple, list] = {}
    out = []
    for v in items:
        if v["live"] == "closed" or v["blocked"]:
            out.append(v)
            continue
        key = (v["lane"], norm(v["employer"]))
        group = shown.setdefault(key, [])
        if len(group) < MAX_CARDS_PER_EMPLOYER:
            group.append(v)
            out.append(v)
        else:
            top = group[0]
            top.setdefault("more_roles", []).append({"title": v["title"], "url": v["url"], "score": v["score"]})
            v["folded_into"] = top["id"]  # kept in the data (so it isn't "new" next week), hidden on the board
            out.append(v)
    return out


def check_one(v: dict, recheck, log) -> dict:
    try:
        return recheck(v)
    except net.Gone:
        return {**v, "live": "closed", "live_note": "The advert page has been taken down."}
    except Exception as e:
        log(f"Couldn't read {v['url']}: {e}")
        return {**v, "live": "unverified", "live_note": "Couldn't open the full advert this week."}


def summarise(items, report, today_s):
    live = [v for v in items if v["live"] != "closed" and not v["blocked"] and not v.get("folded_into")]
    week_end = (date.fromisoformat(today_s) + timedelta(days=7)).isoformat()
    out = {}
    for lane in ("job", "apprenticeship"):
        lv = [v for v in live if v["lane"] == lane]
        out[lane] = {"active": len(lv), "new": sum(v["is_new"] for v in lv),
                     "strong": sum(v["score"] >= 75 for v in lv),
                     "closing_soon": sum(bool(v.get("closes")) and today_s <= v["closes"] <= week_end for v in lv)}
    out["sources_ok"] = sum(r["ok"] for r in report)
    out["sources_failed"] = [r["name"] for r in report if not r["ok"]]
    return out


def load_json(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        return default


def write_json(path: Path, doc):
    path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true", help="fetch live but write nothing")
    ap.add_argument("--rescore", action="store_true", help="re-apply rules and scores to saved data without fetching")
    args = ap.parse_args()
    if args.rescore:
        stored = load_json(DATA / "vacancies.json", {"items": []})["items"]
        keys = sorted({source_key(v["id"]) for v in stored})
        fetchers = [(k, k, (lambda log, k=k: [dict(v, detail_checked=True) for v in stored if source_key(v["id"]) == k]), (lambda v: v)) for k in keys]
        out = run(fetchers=fetchers)
        sys.exit(0)
    out = run(dry_run=args.dry_run)
    failed = out["run"]["summary"]["sources_failed"]
    sys.exit(2 if len(failed) == len(SOURCES) else 0)
