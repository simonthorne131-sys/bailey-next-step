"""Entry-requirement checks against Bailey's confirmed facts. Ported from the Codex build
(scoring.ts requirementChecks). Each check is met / check / not_met. Any not_met keeps the role
out of the main list (it stays under "Everything") with the reason shown. Optional or
'by the start date' wording is only ever a 'check', never a block."""
import re

from .scope import DRIVER_TITLE, LIFT_TRUCK_TITLE, QUALIFIED_TRADE_TITLE, SKILLED_TITLE

OPTIONAL = re.compile(
    r"\b(?:desirable|preferred|preferable|ideally|advantage|advantageous|bonus|not (?:essential|required|necessary)"
    r"|no .{0,30}(?:required|needed|necessary)|training (?:is |will be )?(?:provided|given)|by (?:the )?start|before (?:the )?start"
    r"|willing to (?:obtain|learn|work towards)|working towards|would be (?:great|nice|beneficial)|nice to have|we will train|full training)\b",
    re.I)
ESSENTIAL_WORD = re.compile(r"\b(?:essential|required|requirement|must|need|needed|necessary|mandatory)\b", re.I)
NEGATED = re.compile(r"\b(?:no|not|never|without)\b", re.I)
LIFT_TRUCK = re.compile(r"forklift|reach truck|counterbalance|flt|mhe", re.I)

ORDER = {"met": 0, "check": 1, "not_met": 2}


def _segments(text: str) -> list[tuple[str, bool]]:
    """Split advert text into short lines, marking those in a 'desirable' section."""
    text = re.sub(r"\s*•\s*", "\n", text or "")
    parts = re.split(r"(?<=[.!?])\s+|[;\n]|,\s+(?=(?:a |an |full |valid |current |forklift|ECS|CSCS|driving))|\s+but\s+", text)
    out, desirable = [], False
    for p in parts:
        p = p.strip()
        if not p:
            continue
        if re.match(r"^(?:desirable|nice to have|preferred)\b", p, re.I):
            desirable = True
        elif re.match(r"^(?:essential|skills|other requirements|requirements|what you.ll need|about you)\b", p, re.I):
            desirable = False
        out.append((p, desirable or bool(OPTIONAL.search(p))))
    return out


class Checks:
    def __init__(self):
        self.items: dict[str, dict] = {}

    def add(self, label: str, result: str, note: str):
        cur = self.items.get(label)
        if not cur or ORDER[result] > ORDER[cur["result"]]:
            self.items[label] = {"label": label, "result": result, "note": note}

    def list(self) -> list[dict]:
        return sorted(self.items.values(), key=lambda c: -ORDER[c["result"]])


def requirement_checks(title: str, text: str, profile: dict, lane: str, starter_pay: bool | None = None) -> list[dict]:
    c = Checks()
    full = f"{title}\n{text or ''}"

    if not text or len(text.strip()) < 40 or re.search(r"click apply (?:for|to)|see (?:full )?details", text, re.I):
        c.add("Entry requirements", "check", "The advert doesn't spell out its requirements. Read the full advert before applying.")

    # Contract type
    for line, _ in _segments(full):
        m = re.search(r"zero[ -]hours?|self[ -]employed|commission[ -]only", line, re.I)
        if m and not re.search(r"\b(?:no|not)\b.{0,15}" + re.escape(m.group(0)), line, re.I):
            c.add("Contract", "not_met", f"Advert mentions a {m.group(0).lower()} arrangement, which you ruled out.")

    # Title-level checks
    if DRIVER_TITLE.search(title):
        c.add("Driving licence", "not_met" if profile["driving"] != "full" else "met",
              "This is a driving job, so it needs a full licence. You have a provisional one for now.")
    if LIFT_TRUCK_TITLE.search(title) and not re.search(r"no experience|will train|training provided|trainee", full, re.I):
        c.add("Forklift licence", "met" if profile["forklift"] else "not_met",
              "This job is driving a forklift or reach truck, which needs a licence you don't have yet.")
    if lane == "job" and SKILLED_TITLE.search(title) and not QUALIFIED_TRADE_TITLE.search(title):
        trains = re.search(r"no (?:previous )?experience|will train|full training|training provided|entry[ -]level|trainee|willing to learn|career changer", full, re.I)
        if trains or starter_pay:
            c.add("Skilled role", "check", "The title suggests a skilled job, but the advert or pay hints they'd take someone newer. Check how much experience they want.")
        else:
            c.add("Skilled role", "not_met", "Looks like a job for someone with a few years in the trade, not a starter role.")
    if QUALIFIED_TRADE_TITLE.search(title) and lane == "job":
        c.add("Qualified trade", "not_met" if not profile["professional_electrician"] else "met",
              "This looks like a job for someone already qualified in the trade, not a starter role.")

    for line, optional in _segments(full):
        low = line.lower()
        essential = bool(ESSENTIAL_WORD.search(line))

        # Driving licence (not lift-truck licences)
        if (re.search(r"(?:full|valid|clean|held|driving|uk).{0,35}licen[cs]e|licen[cs]e.{0,30}(?:full|driving)|\bmust (?:drive|be a driver)\b", line, re.I)
                and not LIFT_TRUCK.search(line)):
            if optional:
                c.add("Driving licence", "check", "A driving licence is mentioned as helpful or needed by the start date. You're learning, so check what they expect.")
            elif essential or re.search(r"\b(?:full|valid|held)\b|essential qualifications", line, re.I) or "driving license in" in low:
                if profile["driving"] == "full":
                    c.add("Driving licence", "met", "Full licence required, and you have one.")
                else:
                    c.add("Driving licence", "not_met", "Needs a full driving licence now. You have a provisional one.")
        if re.search(r"own transport|own vehicle|access to (?:a|your own) (?:car|vehicle)|driving essential", line, re.I) and not optional:
            c.add("Getting there", "check", "Asks for your own transport. Lifts or public transport might still work, so check the location and shift times.")

        # Lift trucks, cards
        if re.search(r"(?:forklift|reach truck|counterbalance|flt|mhe).{0,50}(?:licen[cs]e|certificate|certification|ticket|trained|experience)|(?:licen[cs]e|certificate|ticket).{0,30}(?:forklift|reach truck|counterbalance)", line, re.I):
            if optional:
                c.add("Forklift licence", "check", "A forklift licence is a bonus here, not a must. Some employers train you.")
            elif essential or re.search(r"\b(?:valid|current|in[ -]date)\b", line, re.I):
                c.add("Forklift licence", "met" if profile["forklift"] else "not_met", "Needs a forklift licence you already hold.")
        if re.search(r"\bECS\b.{0,30}(?:card|gold)|card.{0,20}\bECS\b", line):
            c.add("ECS card", "check" if optional else ("met" if profile["ecs"] else "not_met"), "Asks for an ECS card." + (" It's optional here." if optional else " You don't have one yet."))
        if re.search(r"\bCSCS\b", line):
            c.add("CSCS card", "check" if (optional or not essential) else ("met" if profile["cscs"] else "not_met"),
                  "Mentions a CSCS card. You'd need to sit the health and safety test to get one." if (optional or not essential)
                  else "Needs a CSCS card before you start. You don't have one yet.")

        # Electrical qualifications and experience
        if re.search(r"\bNVQ\b.{0,45}(?:electrical|electrotechnical)|(?:electrical|electrotechnical).{0,45}\bNVQ\b", line, re.I) and not optional:
            c.add("Electrical NVQ", "met" if profile["nvq_electrical"] else "not_met",
                  "Asks for an electrical NVQ. Your Level 3 is a college qualification, which isn't the same thing.")
        if re.search(r"\b(?:AM2|18th edition|2391|2382|JIB|gold card)\b", line, re.I):
            c.add("Trade certificates", "check" if optional else "not_met",
                  "Mentions trade certificates (18th Edition, AM2 or JIB) that qualified electricians hold." + (" Listed as a bonus." if optional else ""))
        if (re.search(r"(?:qualified|competent|approved|experienced) electrician|(?:commercial|industrial|domestic|on[ -]site).{0,25}(?:electrical|electrician).{0,30}experience"
                      r"|\d+\+?\s*years?.{0,35}(?:electrical|electrician)", line, re.I)
                and not re.search(r"alongside|under (?:the )?supervision|become (?:a|an) (?:qualified|competent)|support(?:ing)?|assist|work with", line, re.I)
                and not optional):
            c.add("Electrical experience", "not_met", "Wants someone with paid electrical work experience. Your experience so far is from college.")
        if re.search(r"level\s*3.{0,45}electrical|electrical.{0,45}level\s*3", line, re.I) and "nvq" not in low:
            c.add("Level 3 Electrical", "met", "Mentions Level 3 electrical. You've achieved Level 3 Electrical Installation at college.")
        elif re.search(r"level\s*2.{0,45}electrical|electrical.{0,45}level\s*2", line, re.I) and "nvq" not in low:
            c.add("Electrical qualification", "met", "Asks for Level 2 electrical. You've gone further and achieved Level 3.")

        # Age
        m = re.search(r"minimum age (?:is |of )?(\d+)|(?:must|need).{0,20}(?:aged?|over the age of|at least)\s*(\d+)|\b(\d{2})\s*\+?\s*(?:years? )?(?:or over|and over)", line, re.I)
        if m and not optional:
            age = int(next(g for g in m.groups() if g)) + (1 if "over the age of" in low else 0)
            if 16 <= age <= 30:
                c.add("Age", "met" if profile["age"] >= age else "not_met", f"Minimum age {age}. You're {profile['age']}.")

        # GCSEs
        if re.search(r"\bGCSE", line, re.I):
            gm = re.search(r"grade\s*\(?\s*([4-9])|(?:minimum|at least)\s+(?:grade\s*)?([4-9])|\(\s*([4-9])\s*\)|grade\s*c\b|\b([4-9])\s*\(?c\)?\b", line, re.I)
            need = 4 if gm and not any(gm.groups()) else (int(next((g for g in gm.groups() if g), 4)) if gm else None)
            for subject in ("maths", "english", "science"):
                if subject in low or (subject == "maths" and "mathematics" in low):
                    have = profile["gcse"].get(subject)
                    label = f"GCSE {subject.title()}"
                    if need is None:
                        c.add(label, "met" if have else "check", f"Asks for GCSE {subject.title()}." + (f" You have grade {have}." if have else " Not recorded for you."))
                    elif have is None:
                        c.add(label, "check", f"Asks for GCSE {subject.title()} at grade {need}. Your grade isn't recorded.")
                    elif have >= need:
                        c.add(label, "met", f"Asks for GCSE {subject.title()} grade {need}. You have {have}.")
                    elif have == need - 1 and not optional:
                        c.add(label, "check", f"Asks for GCSE {subject.title()} grade {need}. You have {have}. Your Level 3 may count as equivalent, so it's worth asking.")
                    else:
                        c.add(label, "check" if optional else "not_met", f"Asks for GCSE {subject.title()} grade {need}. You have {have}.")

        # Other experience the advert insists on
        if (re.search(r"(?:must|essential|required|need).{0,80}experience|experience.{0,35}(?:essential|required)|minimum.{0,30}years|\d+\+?\s*years?'?\s*(?:of\s+)?experience", line, re.I)
                and not optional and not re.search(r"electric|licen[cs]e|forklift", line, re.I)):
            if re.search(r"warehouse|picking|stock", line, re.I) and profile["warehouse"]:
                c.add("Experience", "met", "Wants warehouse experience, which you have.")
            elif re.search(r"production|assembly|manufactur", line, re.I) and profile["production"]:
                c.add("Experience", "met", "Wants production experience, which you have.")
            elif re.search(r"customer service|retail|hospitality|food", line, re.I) and profile["customer_service"]:
                c.add("Experience", "met", "Wants customer service experience. You have plenty from your current job.")
            else:
                c.add("Experience", "check", "Asks for some experience: " + line[:140].rstrip(".") + ".")

        # Screening
        if re.search(r"\b(?:DBS|security clearance|SC clearance|BPSS|citizenship|nationality)\b", line, re.I):
            c.add("Background checks", "check", "Involves background or security checks. Usually fine, but worth knowing.")

    return c.list()


def blocked(checks: list[dict]) -> bool:
    return any(ch["result"] == "not_met" for ch in checks)
