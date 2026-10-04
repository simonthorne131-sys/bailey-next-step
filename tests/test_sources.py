"""Source readers, tested offline against real pages saved on 4 Oct 2026."""
import json
from pathlib import Path

import pytest

from scout import net
from scout.sources import faa, reed, wpjobs
from scout.sources.common import miles_for, parse_uk_date, pay_from_text

FX = Path(__file__).parent / "fixtures"


def read(name):
    return (FX / name).read_text(encoding="utf-8")


def test_faa_search_page():
    items, total, nxt = faa.parse_search(read("faa-search.html"), faa.ORIGIN + "/apprenticeships")
    assert total > 100 and len(items) == 10
    rac = next(i for i in items if "RAC" in i["title"])
    assert rac["id"] == "faa:VAC2000052571"
    assert rac["distance_miles"] == 1.5
    assert rac["pay_annual"] == 16500 and rac["pay_hourly"] is None
    assert rac["closes"] == "2026-10-15"
    assert rac["level"] == 2
    assert nxt and "pageNumber=2" in nxt
    external = [i for i in items if not i["checkable"]]
    assert external and all(i["apply_route"].startswith("Apply on") for i in external)


def test_faa_advert_page():
    base, *_ = faa.parse_search(read("faa-search.html"), faa.ORIGIN)
    rac = next(i for i in base if "RAC" in i["title"])
    v = faa.parse_detail(read("faa-advert.html"), rac)
    assert v["live"] == "open" and v["detail_checked"]
    assert "37 hours a week" in v["hours_text"]
    assert "FULL UK MANUAL LICENSE" in v["requirements"]


def test_faa_closed_page():
    v = faa.parse_detail("<html><main><h1>Page not found</h1></main></html>", {"title": "x"})
    assert v["live"] == "closed"


def test_faa_unrecognised_page_is_an_error_not_closed():
    with pytest.raises(net.FetchError):
        faa.parse_detail("<html><main><h1>Something else</h1></main></html>", {"title": "x"})


def test_faa_search_without_heading_is_an_error_not_zero():
    with pytest.raises(net.FetchError):
        faa.parse_search("<html><h1>Service unavailable</h1></html>", faa.ORIGIN)


def test_reed_search_and_advert():
    items = reed.parse_search(read("reed-search.html"))
    assert len(items) == 25
    first = items[0]
    assert first["id"] == "reed:57406837" and first["lane"] == "job"
    assert first["pay_annual"] == 29000 and first["pay_text"].startswith("£29,000")
    hourly = [i for i in items if i["pay_hourly"]]
    assert hourly and all(5 < i["pay_hourly"] < 60 for i in hourly)
    v = reed.parse_detail(read("reed-advert.html"), first)
    assert v["live"] == "open" and v["contract"] == "Permanent"
    assert "Monday to Friday" in (v["pattern_text"] or "")
    assert v["closes"] == "2026-10-15"


def test_wordpress_agency_feeds():
    for name, agency in (("insight-feed.json", wpjobs.AGENCIES[1]), ("rapier-feed.json", wpjobs.AGENCIES[0])):
        records = json.loads(read(name))
        items = [wpjobs.from_record(r, agency) for r in records]
        assert items and all(i["id"].startswith(agency["key"] + ":") for i in items)
        assert all(i["live"] in ("open", "closed") for i in items)
    insight = [wpjobs.from_record(r, wpjobs.AGENCIES[1]) for r in json.loads(read("insight-feed.json"))]
    assert any("agency; employer not named" in i["employer"] for i in insight)


def test_helpers():
    assert parse_uk_date("Closes in 5 days (Friday 9 October 2026 at 11:59pm)") == "2026-10-09"
    assert parse_uk_date("Closing Date: 15 of October 2026") == "2026-10-15"
    assert parse_uk_date("no date") is None
    assert miles_for("Bletchley, Milton Keynes") == 4
    assert miles_for("Milton Keynes (MK6 5BE) and 15 other locations") == 3
    assert miles_for("Somewhere Unknown") is None
    assert pay_from_text("£12.71 - £13.21 per hour") == (12.71, None)
    assert pay_from_text("£16,500 a year") == (None, 16500)
    assert pay_from_text("Competitive") == (None, None)
