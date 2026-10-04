"""The weekly pipeline with fake sources: liveness, failures, dedupe and closing dates."""
import json
from datetime import date

import pytest

from scout import net, run as runmod


def item(vid, title="Warehouse Operative", employer="Acme", location="Milton Keynes", **kw):
    v = {"id": vid, "source": "Fake", "lane": "job", "title": title, "employer": employer, "location": location,
         "distance_miles": 2.0, "url": f"https://example.org/{vid}", "text": "Monday to Friday. Full training provided.",
         "hours_text": "40 hours per week", "pay_hourly": 13.5, "pay_text": "£13.50 per hour", "checkable": True,
         "detail_checked": True, "live": "open"}
    v.update(kw)
    return v


@pytest.fixture
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(runmod, "DATA", tmp_path)
    return tmp_path


def source(key, items=None, error=None, recheck=None):
    def fetch_all(log):
        if error:
            raise error
        return [dict(i) for i in items or []]
    return (key, key.title(), fetch_all, recheck or (lambda v: v))


def test_empty_run_writes_valid_files(data_dir):
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [])])
    assert out["items"] == []
    assert json.loads((data_dir / "run.json").read_text())["summary"]["sources_ok"] == 1


def test_failed_source_is_reported_and_old_adverts_not_closed(data_dir):
    runmod.run(today=date(2026, 10, 3), fetchers=[source("fake", [item("fake:1")])])
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", error=net.FetchError("HTTP 503"))])
    assert out["run"]["summary"]["sources_failed"] == ["Fake"]
    v = out["items"][0]
    assert v["live"] == "unverified" and v["first_seen"] == "2026-10-03"


def test_advert_gone_is_closed(data_dir):
    runmod.run(today=date(2026, 10, 3), fetchers=[source("fake", [item("fake:1")])])

    def gone(v):
        raise net.Gone("HTTP 410")
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [], recheck=gone)])
    assert out["items"][0]["live"] == "closed"


def test_timeout_is_unverified_not_closed(data_dir):
    runmod.run(today=date(2026, 10, 3), fetchers=[source("fake", [item("fake:1")])])

    def flaky(v):
        raise net.FetchError("timeout")
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [], recheck=flaky)])
    assert out["items"][0]["live"] == "unverified"


def test_closing_date_passed_is_closed(data_dir):
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [item("fake:1", closes="2026-10-01")])])
    assert out["items"][0]["live"] == "closed"


def test_duplicates_merge_and_keep_links(data_dir):
    a = item("fake:1", employer="Acme Ltd", location="Milton Keynes, Bucks")
    b = item("other:9", employer="ACME", location="Milton Keynes", url="https://elsewhere.example/9")
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [a]), source("other", [b])])
    assert len(out["items"]) == 1
    assert out["items"][0]["other_links"] == ["https://elsewhere.example/9"]


def test_out_of_scope_roles_dropped(data_dir):
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [item("fake:1", title="IT Support Technician"), item("fake:2", title="Head Chef")])])
    assert out["items"] == []


def test_new_flag_and_first_seen_kept(data_dir):
    runmod.run(today=date(2026, 10, 3), fetchers=[source("fake", [item("fake:1")])])
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [item("fake:1"), item("fake:2", title="Production Operative")])])
    by = {v["id"]: v for v in out["items"]}
    assert by["fake:1"]["is_new"] is False and by["fake:1"]["first_seen"] == "2026-10-03"
    assert by["fake:2"]["is_new"] is True


def test_blocked_roles_stay_listed_with_reason(data_dir):
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [item("fake:1", title="Counterbalance Forklift Driver", text="Must have in-date counterbalance licence")])])
    v = out["items"][0]
    assert v["blocked"] and any(c["result"] == "not_met" for c in v["checks"])


def test_same_role_at_several_branches_is_one_card_nearest_first(data_dir):
    a = item("fake:1", employer="Nova", title="Apprentice Technician", location="Luton", distance_miles=19.0)
    b = item("fake:2", employer="Nova", title="Apprentice Technician", location="Bletchley", distance_miles=4.0)
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [a, b])])
    assert len(out["items"]) == 1
    assert out["items"][0]["location"] == "Bletchley" and out["items"][0]["other_locations"] == ["Luton"]


def test_repeated_pay_word_is_tidied(data_dir):
    out = runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [item("fake:1", pay_text="Competitive Competitive wage offered", pay_hourly=None)])])
    assert out["items"][0]["pay_text"] == "Competitive wage offered"


def test_rescore_keeps_search_date_sources_and_new_flags(data_dir):
    runmod.run(today=date(2026, 10, 3), fetchers=[source("fake", [item("fake:1")])])
    runmod.run(today=date(2026, 10, 10), fetchers=[source("fake", [item("fake:1"), item("fake:2", title="Production Operative")])])
    before = json.loads((data_dir / "run.json").read_text())
    runmod.rescore_saved()
    after = json.loads((data_dir / "run.json").read_text())
    items = {v["id"]: v for v in json.loads((data_dir / "vacancies.json").read_text())["items"]}
    assert after["today"] == before["today"] and after["sources"] == before["sources"] and "rescored_at" in after
    assert items["fake:2"]["is_new"] is True and items["fake:1"]["is_new"] is False
    assert items["fake:1"]["first_seen"] == "2026-10-03"
