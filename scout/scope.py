"""What is in or out of Bailey's search. Ported from the Codex build (career-scope.ts and
job-scope.ts) with one fix: practical telecoms/cabling titles are kept even if they mention
software. Filtering looks at the role title and training course, never the employer name."""
import re

SOFTWARE = re.compile(
    r"\b(?:software|web\s+(?:developer|development|designer)|(?:mobile\s+)?app(?:lication)?s?\s+(?:developer|development)"
    r"|front[ -]?end|back[ -]?end|full[ -]?stack|devops|cyber\s*security|data\s+(?:analyst|analysis|scientist|science)"
    r"|business intelligence|programmer|coder)\b", re.I)
GENERAL_IT = re.compile(
    r"\b(?:(?:IT|ICT)\s+(?:support|technician|engineer|apprentice|apprenticeship|service|systems?|network|infrastructure|operations|solutions|helpdesk)"
    r"|information\s+(?:technology|communications?)|digital\s+(?:support|service|solutions|marketing)|(?:service|help)\s*desk"
    r"|desktop\s+support|computer\s+(?:support|technician|systems)|cloud\s+(?:support|engineer|technician|infrastructure)"
    r"|network\s+(?:engineer|administrator)|systems?\s+(?:administrator|engineer|support)|technical\s+support)\b", re.I)
PRACTICAL_KEEP = re.compile(
    r"\b(?:radio\s+network|telecom(?:munication)?s?|data\s+cabl\w*|network\s+cabl\w*|structured\s+cabl\w*|(?:fibre|fiber)[ -]optic"
    r"|(?:fibre|fiber)\s+(?:engineer|technician|installer)|electrical\s+controls?|controls?\s+(?:systems?|engineer|technician)"
    r"|instrumentation|PLC|SCADA)\b", re.I)
MANDARIN = re.compile(r"\bmandarin[ -]+(?:speaking|speaker)\b", re.I)
TOO_SENIOR = re.compile(
    r"\b(?:manager|director|head of|senior|supervisor|team leader|lead|principal|trainer|planner|estimator|surveyor|buyer|"
    r"consultant|recruiter|designer|design engineer|sales engineer|field sales|account manager|coordinator)\b", re.I)

ELECTRICAL = re.compile(
    r"electrical|electrician|electronics?|wireperson|radio|telecom|data cabling|fire.{0,15}security|controls|solar|"
    r"EV charg|renewable|wind turbine", re.I)
PRACTICAL = re.compile(
    r"electrical|electrician|electronics|engineer|engineering|mechanic|mechanical|maintenance|automotive|vehicle|autocare|"
    r"marine|seagoing|wind turbine|renewable|solar|EV (?:charg|infrastructure)|building services|facilities|fire.{0,15}security|"
    r"radio|telecom|cabling|controls|instrumentation|technician|fitter|installer|plumb|heating|hvac|gas|refrigeration|"
    r"manufactur|welding|fabricat|machin|cnc|rail|lift (?:engineer|technician)|multi.?skilled", re.I)
CONSTRUCTION = re.compile(r"construction|bricklay|carpent|joiner|plaster|steel fix|scaffold|roof|site operative|groundwork|civil", re.I)

JOB_CATEGORIES = [
    ("Electrical starter role", re.compile(
        r"electrician'?s?\s*mate|electrical\s+(?:mate|labourer|assistant|trainee|improver|apprentice)|trainee\s+electrician|"
        r"electrical\s+installer|improver\s+electrician|apprentice\s+electrician", re.I)),
    ("Trade counter", re.compile(r"trade[ -]?counter|branch assistant|counter (?:sales|assistant)", re.I)),
    ("Practical starter role", re.compile(
        r"\b(?:trainee|assistant|junior|mate|labourer|apprentice|entry[ -]level|helper|improver)\b.*?(?:" + PRACTICAL.pattern + r")"
        r"|(?:" + PRACTICAL.pattern + r").*?\b(?:trainee|assistant|junior|mate|labourer|apprentice|helper|improver|operative)\b"
        r"|site operative|general labourer|multi.?skilled operative|maintenance operative|facilities assistant|machine minder", re.I)),
    ("Warehouse", re.compile(
        r"warehouse|stores? (?:assistant|operative|person)|storekeeper|stock (?:assistant|controller)|pick(?:er|ing)|pack(?:er|ing)|"
        r"goods (?:in|out)|loader|despatch|dispatch|logistics operative|forklift|reach truck|counterbalance", re.I)),
    ("Production", re.compile(r"production|manufacturing (?:operative|assistant)|assembly|assembler|machine operator|process operative", re.I)),
    ("Retail", re.compile(r"retail|sales (?:assistant|adviser|advisor)|shop assistant|store colleague|customer assistant|store assistant", re.I)),
    ("Office / admin", re.compile(r"admin|office assistant|receptionist|customer service|data entry|clerk", re.I)),
]

# Titles that are, on their face, for people already qualified or licensed to drive.
QUALIFIED_TRADE_TITLE = re.compile(
    r"^(?!.*\b(?:mate|trainee|apprentice|assistant|labourer|improver|helper)\b).*\b(?:electrician|wireperson|electrical engineer|"
    r"gas engineer|plumber|carpenter|joiner|bricklayer|plasterer|welder|hgv|c\+e|class 1|class 2)\b", re.I)
DRIVER_TITLE = re.compile(r"^(?!.*\bmate\b)(?!.*\b(?:forklift|reach|counterbalance|flt|mhe|truck)\b).*\b(?:driver|courier)\b", re.I)
SKILLED_TITLE = re.compile(
    r"^(?!.*\b(?:mate|trainee|apprentice|assistant|labourer|improver|helper|junior|entry[ -]level|operative)\b).*"
    r"\b(?:engineer|technician|fitter|mechanic|electrician|installer|machinist|welder|fabricator|assembler|inspector)\b", re.I)
LIFT_TRUCK_TITLE = re.compile(r"\b(?:forklift|reach truck|reach|counterbalance|flt|mhe)\b", re.I)


def career_excluded(title: str, course: str = "") -> str | None:
    """Return a reason if this role is outside Bailey's search, else None."""
    t = re.sub(r"[‐-―]", "-", title)
    if MANDARIN.search(t):
        return "Mandarin-speaking role (removed from the search)"
    if PRACTICAL_KEEP.search(t):
        return None
    if SOFTWARE.search(t) or GENERAL_IT.search(t) or re.search(r"\bIT\b", t):
        return "Software or general IT role (removed from the search)"
    if course and (SOFTWARE.search(course) or GENERAL_IT.search(course) or re.search(r"information communications technician|digital", course, re.I)):
        return "Software or general IT training (removed from the search)"
    return None


def job_category(title: str) -> str | None:
    if career_excluded(title) or TOO_SENIOR.search(title):
        return None
    for name, pattern in JOB_CATEGORIES:
        if pattern.search(title):
            return name
    if QUALIFIED_TRADE_TITLE.search(title) or DRIVER_TITLE.search(title) or SKILLED_TITLE.search(title):
        return "Skilled role"  # kept so the requirement check can explain why it's not for now
    return None


ENGINEERING = re.compile(
    r"engineer|engineering|maintenance|mechatronic|electronic|marine|seagoing|submarin|renewable|wind turbine|solar|hvac|"
    r"air conditioning|refrigeration|building services|telecom|instrumentation|controls|multi.?skilled|lift (?:engineer|technician)|rail", re.I)
VEHICLE_MANUFACTURING = re.compile(
    r"vehicle|automotive|motor|mechanic|autocare|technician|manufactur|fabricat|welding|welder|sheet metal|machin|cnc|composite|"
    r"production|assembly|plumb|heating|gas", re.I)


def apprenticeship_category(title: str, course: str = "") -> str:
    text = f"{title} {course}"
    if re.search(r"vehicle|motor|automotive|\bMET\b|autocare|car body|paint technician", title, re.I) and not re.search(r"auto.?electric", title, re.I):
        return "Vehicle and manufacturing"
    if ELECTRICAL.search(title) or re.search(r"electrical|electrotechnical|installation electrician|electronic", course or "", re.I):
        return "Electrical"
    if re.search(r"footwear|bakery|food|textile|hair|beauty|retail|business|account|hospitality|care", text, re.I):
        return "Other"
    if ENGINEERING.search(text):
        return "Engineering"
    if VEHICLE_MANUFACTURING.search(text):
        return "Vehicle and manufacturing"
    if CONSTRUCTION.search(text):
        return "Construction trade"
    return "Other"
