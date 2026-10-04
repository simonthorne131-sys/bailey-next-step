"""Matching criteria. Facts confirmed by Simon (27 Sep and 4 Oct 2026). No contact details,
surname or health information belong in this file: the repository is public.
Unknown facts stay None and are treated as 'check', never guessed."""
import re

PROFILE = {
    "age": 19,
    "electrical_college_level": 3,       # Electrical Installation Level 3, college (not an NVQ)
    "gcse": {"maths": 4, "english": 4, "science": None},
    "english_subject": None,              # Language / Literature not recorded
    "practical_electrical": True,         # college practicals: wiring, conduit, tray, test kit
    "electrical_industry_experience": False,
    "professional_electrician": False,
    "nvq_electrical": False,
    "driving": "provisional",            # owns a car, taking lessons; no full licence yet
    "forklift": False,
    "ecs": False,
    "cscs": False,
    "warehouse": True,
    "production": True,
    "customer_service": True,
    "relocation": True,
    "seagoing": True,
    "max_commute_minutes": 30,
    "prefer_full_time": True,
    "prefer_weekdays": True,
    "prefer_daytime": True,
    "prefer_routine": True,
    "prefer_quieter": True,
    # Exact McDonald's rate not known. Simon (4 Oct 2026): below the adult £12.71, as he is 19.
    # £10.85 = 18-20 National Minimum Wage from April 2026. Shown as "roughly".
    "current_hourly": 10.85,
    "current_hourly_confirmed": False,
}

WEIGHTS = {
    "apprenticeship": {"career": 30, "travel": 25, "evidence": 15, "hours": 10, "shifts": 10, "pay": 5, "workplace": 5},
    "job": {"career": 25, "pay": 20, "travel": 20, "hours": 10, "shifts": 10, "evidence": 10, "workplace": 5},
}

BANDS = [(75, "Strong match"), (60, "Worth a look"), (0, "Weaker match")]

# Straight-line miles from home (central Milton Keynes), rounded. Used only when a source gives a town and no
# distance. Shown as "about N miles"; never presented as a journey time.
TOWN_MILES = {
    "milton keynes": 3, "central milton keynes": 1, "campbell park": 1, "bletchley": 4, "fenny stratford": 3,
    "wolverton": 5, "stony stratford": 6, "newport pagnell": 4, "olney": 9, "wymbush": 4, "kiln farm": 5,
    "kingston": 3, "kents hill": 2, "tongwell": 3, "crownhill": 3, "knowlhill": 2, "denbigh": 3,
    "wavendon": 3, "woburn sands": 5, "broughton": 2, "magna park": 3, "fairfields": 5, "brinklow": 3,
    "cranfield": 8, "ridgmont": 8, "marston moretaine": 9, "woburn": 7, "bow brickhill": 4,
    "winslow": 12, "buckingham": 13, "leighton buzzard": 10, "towcester": 11, "silverstone": 15,
    "bedford": 15, "kempston": 14, "ampthill": 12, "flitwick": 14, "northampton": 16, "brackley": 21,
    "luton": 19, "dunstable": 17, "aylesbury": 18, "haddenham": 24, "tring": 20, "bicester": 24,
    "daventry": 24, "wellingborough": 20, "rushden": 21, "sandy": 22, "biggleswade": 22, "hitchin": 24,
    "stevenage": 27, "hemel hempstead": 27, "kettering": 27, "banbury": 30, "oxford": 37, "st albans": 31,
    "high wycombe": 33, "watford": 33, "cambridge": 40, "coventry": 46, "london": 47,
}

# Employers that are electrical wholesalers/distributors (trade counter roles rank higher there).
ELECTRICAL_WHOLESALERS = re.compile(
    r"city electrical|\bcef\b|edmundson|rexel|denmans|newey|yesss|electric center|\btlc\b|"
    r"wholesale electrical|electrical wholesal|eurolec|electrical distributor|screwfix|toolstation|"
    r"medlock|wf senate|senate electrical|anixter|cromwell|rs components|rs group",
    re.I,
)
