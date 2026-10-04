"""Scope, entry-requirement and scoring rules: the distinctions the brief says must hold."""
from scout.checks import blocked, requirement_checks
from scout.profile import PROFILE
from scout.scope import career_excluded, job_category
from scout.scoring import score


def results(title, text, lane="job"):
    return {c["label"]: c["result"] for c in requirement_checks(title, text, PROFILE, lane)}


# ---- scope ----
def test_it_and_software_are_out_but_practical_cabling_stays():
    assert career_excluded("Software Developer Apprentice")
    assert career_excluded("IT Support Apprentice")
    assert career_excluded("Helpdesk Analyst")
    assert career_excluded("Trainee", "Information communications technician (level 3)")
    assert not career_excluded("Data Cabling Engineer Trainee")
    assert not career_excluded("Telecoms Apprentice")
    assert not career_excluded("Electrical Controls Technician Apprentice")


def test_mandarin_roles_are_out():
    assert career_excluded("Mandarin-speaking Customer Service Adviser")


def test_job_categories():
    assert job_category("Electrician's Mate") == "Electrical starter role"
    assert job_category("Trade Counter Assistant") == "Trade counter"
    assert job_category("Maintenance Assistant") == "Practical starter role"
    assert job_category("Warehouse Operative") == "Warehouse"
    assert job_category("Production Operative") == "Production"
    assert job_category("Retail Assistant") == "Retail"
    assert job_category("Admin Assistant") == "Office / admin"
    assert job_category("Warehouse Manager") is None
    assert job_category("Senior Electrical Engineer") is None
    assert job_category("Chef de Partie") is None


# ---- requirements ----
def test_college_level3_is_not_an_nvq_or_qualified_electrician():
    r = results("Electrical Improver", "Must hold NVQ Level 3 Electrotechnical")
    assert r["Electrical NVQ"] == "not_met"
    r = results("Electrician", "Qualified electrician required")
    assert r["Qualified trade"] == "not_met"
    r = results("Electrical Apprentice", "Level 3 Electrical Installation would be an advantage", "apprenticeship")
    assert r["Level 3 Electrical"] == "met"


def test_provisional_licence_vs_full_licence():
    assert results("RAC Mobile Mechanic", "Essential qualifications DRIVING LICENSE in: FULL UK MANUAL LICENSE")["Driving licence"] == "not_met"
    assert results("Engineer Trainee", "A full driving licence is desirable")["Driving licence"] == "check"
    assert results("Engineer Trainee", "You must have a full UK driving licence by the start date")["Driving licence"] == "check"
    assert results("Van Driver", "Great pay")["Driving licence"] == "not_met"
    assert "Driving licence" not in results("Van Driver/Drivers Mate", "Help with deliveries")


def test_forklift_and_cards():
    assert results("Counterbalance Forklift Driver", "Must have an in-date counterbalance licence")["Forklift licence"] == "not_met"
    assert "Driving licence" not in results("Reach Forklift Driver", "Reach truck experience needed")
    assert results("Warehouse Operative", "Forklift licence desirable but not essential")["Forklift licence"] == "check"
    assert results("Site Operative", "Candidates need to have a CSCS card")["CSCS card"] == "not_met"
    assert results("Site Operative", "CSCS card is an advantage")["CSCS card"] == "check"
    assert results("Electrician's Mate", "ECS card required")["ECS card"] == "not_met"


def test_contracts_and_age_and_gcse():
    assert results("Warehouse Operative", "This is a zero hours contract")["Contract"] == "not_met"
    assert "Contract" not in results("Warehouse Operative", "No zero hours contracts here")
    assert results("Apprentice", "Minimum age is 21", "apprenticeship")["Age"] == "not_met"
    assert results("Apprentice", "Minimum age 17", "apprenticeship")["Age"] == "met"
    assert results("Apprentice", "GCSE English and Maths at grade 4 or above", "apprenticeship")["GCSE Maths"] == "met"
    assert results("Apprentice", "GCSE Maths grade 6 required", "apprenticeship")["GCSE Maths"] == "not_met"
    assert results("Apprentice", "GCSE Science grade 4", "apprenticeship")["GCSE Science"] == "check"


def test_electrical_experience_under_supervision_is_fine():
    assert "Electrical experience" not in results("Electrician's Mate", "Work alongside a qualified electrician on site")
    assert results("Electrical Improver", "Minimum 2 years electrical experience required")["Electrical experience"] == "not_met"


# ---- scoring ----
def vac(**kw):
    v = {"lane": "job", "title": "Warehouse Operative", "employer": "Acme", "location": "Milton Keynes", "distance_miles": 3.0,
         "pay_text": None, "pay_hourly": None, "pay_annual": None, "hours_text": None, "pattern_text": None, "text": "", "category": "Warehouse"}
    v.update(kw)
    v["checks"] = requirement_checks(v["title"], v["text"], PROFILE, v["lane"])
    return v


def test_unknowns_are_half_marks_and_widen_range():
    s = score(vac())
    assert s["score_low"] < s["score"] < s["score_high"]
    assert any("Pay not stated" in g for g in s["gaps"])


def test_better_pay_scores_higher_in_jobs_lane():
    low = score(vac(pay_hourly=10.5))["score"]
    high = score(vac(pay_hourly=13.0))["score"]
    assert high > low


def test_full_time_is_preferred_not_penalised():
    ft = score(vac(hours_text="40 hours per week"))
    pt = score(vac(hours_text="16 hours per week"))
    assert ft["score"] > pt["score"]


def test_nights_rank_lower_but_stay_visible():
    day = vac(pattern_text="Monday to Friday 8am-4pm")
    night = vac(pattern_text="Night shift 10pm-6am")
    assert score(day)["score"] > score(night)["score"]
    assert not blocked(night["checks"])


def test_electrical_apprenticeship_outranks_warehouse_job_style_role():
    appr = vac(lane="apprenticeship", title="Electrical Installation Apprentice", category="Electrical",
               training="Installation electrician (level 3)", hours_text="37.5 hours a week", pattern_text="Monday to Friday")
    other = vac(lane="apprenticeship", title="Hairdressing Apprentice", category="Other", hours_text="37.5 hours a week")
    assert score(appr)["score"] > score(other)["score"]
    assert score(appr)["band"] in ("Strong match", "Worth a look")


# ---- added 4 Oct after first live run ----
def test_experienced_engineer_jobs_are_not_starter_roles():
    assert job_category("Maintenance Engineer") == "Skilled role"
    assert results("Maintenance Engineer", "Shift allowance, great benefits")["Skilled role"] == "not_met"
    assert results("Workshop Technician", "Full training provided")["Skilled role"] == "check"
    assert job_category("Field Sales Engineer") is None
    assert job_category("Vehicle Technician Trainer") is None
    assert job_category("Planner - Electrical & Gas") is None
    assert job_category("Junior Electrical Maintenance Engineer") == "Practical starter role"


def test_apprenticeship_categories_put_electrical_first():
    from scout.scope import apprenticeship_category as cat
    assert cat("Electrical apprentice") == "Electrical"
    assert cat("Apprentice", "Installation electrician and maintenance electrician (level 3)") == "Electrical"
    assert cat("Apprentice Air Conditioning Engineer") == "Engineering"
    assert cat("Service Technician Apprenticeship") == "Vehicle and manufacturing"
    assert cat("Footwear Apprentice", "Footwear manufacturer (level 2)") == "Other"


def test_one_gcse_grade_short_is_worth_asking_not_a_block():
    assert results("Apprentice", "GCSE Maths grade 5 required", "apprenticeship")["GCSE Maths"] == "check"
    assert results("Apprentice", "GCSE Maths grade 6 required", "apprenticeship")["GCSE Maths"] == "not_met"


def test_far_apprenticeship_is_capped_below_strong_but_sea_roles_are_not():
    far = vac(lane="apprenticeship", title="Electrical Apprentice", category="Electrical", distance_miles=60.0,
              hours_text="37.5 hours a week", pattern_text="Monday to Friday", pay_annual=20000)
    assert score(far)["score"] <= 74
    near = dict(far, distance_miles=3.0)
    assert score(near)["score"] >= 75


def test_electrically_qualified_or_time_served_is_a_block():
    assert results("Junior Electrical Maintenance Engineer", "You will be electrically qualified with maintenance experience")["Electrical qualification"] == "not_met"
    assert results("Electrician's Mate", "Time-served electrician required")["Electrical qualification"] == "not_met"
    assert "Electrical qualification" not in results("Trainee Electrician", "We will support you to become fully qualified")
