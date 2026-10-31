"""Build statusmap.json: the Kings of Ruin verse graph with every status gain and status condition.

Usage: python -I -X utf8 statusmap.py pulled statusmap.json

English text is parsed (its wording is regular); Polish labels and status names ride along by element.
"""
import collections
import json
import re
import sqlite3
import sys
from pathlib import Path

CAMP, EN, PL = 26, 1, 2

src, out = Path(sys.argv[1]), Path(sys.argv[2])
con = sqlite3.connect(f"file:{src / 'appData.sqlite'}?mode=ro", uri=True)


def clean(t):
    t = re.sub(r"<[^>]*>|@\w+@", " ", t or "")
    t = re.sub(r"\s*\((Chapter [^)]*)\)\s*”", r": \1”", t)  # keep "(" inside a status name from splitting clauses
    t = t.replace("''", "”")  # one text closes a status name with two apostrophes
    return re.sub(r"\s+", " ", t).strip()


def texts(lang):
    return {e: clean(t) for e, t in con.execute("select _idElem, text from ElemetText where _idLang=?", (lang,))}


en, pl = texts(EN), texts(PL)
choice_txt = {(ch, lang): (clean(r), clean(s)) for ch, lang, r, s in con.execute(
    "select _idChoice, _idLang, reqTxt, resTxt from ChoiceInfoText where _idLang in (?, ?)", (EN, PL))}

loc_num = dict(con.execute("select _id, displayNumber from Location where _campId=?", (CAMP,)))
verses = {vid: {"loc": loc_num[l], "num": n, "text_pl": "", "leads_pl": [], "gains": [], "choices": []}
          for vid, l, n in con.execute("select _id, _locationId, displayNumber from Verse") if l in loc_num}

ALIAS = {"s mall favor": "Small Favor", "small favors": "Small Favor", "times passes": "Time Passes"}  # typos in the source texts
STATUS = re.compile(r"(?:[“\"]\s*([^“”\"]{1,40}?)\s*[”\"]|(?<!\w)'\s*([^'“”\"]{1,40}?)\s*')(?:\s*part\s*(\d+))?\s*status")
COUNT = re.compile(r"at least (\w+) parts? of the\s*$", re.I)  # "at least two parts of the “X” status"
NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
HERO = r"(Elgan|Gerdwyn|Iunis|Osbert)"
# "requires Elgan or Gerdwyn", "If you're playing Iunis", "If Osbert is in this Location"
HEROES = re.compile(rf"(?:requires|playing|[Ii]f)\s+{HERO}(?:\s*(?:,\s*|\s+or\s+){HERO})?(?:\s+or\s+{HERO})?")
VERB = re.compile(r"\b(gain|don’t have|don't have|do not have|lack|have|requires?)\b", re.I)
LEAD = re.compile(r"Nowa Wskazówka:\s*(.+)", re.I)  # the game's own spoiler-free pointers
CHAPTER = re.compile(r"playing (Chapter [^,.)]*?)(?=\s*(?:,|\.|\)|$| or if| and))")


def canon(s):
    s = s.replace("Passess", "Passes").replace("'", "’")
    k = s.casefold()
    return ALIAS.get(k) or CASE.setdefault(k, s)


CASE = {}


def mentions(t):
    """[(verb, status, part, conds)] where verb is 'gain', 'have' or 'not'; the verb is the nearest one before it
    in its clause, and conds are the have/not mentions earlier in that clause ("If you have A, gain B")."""
    res = []
    for seg in re.split(r"[.○●(;]", t):
        conds = []
        for m in STATUS.finditer(seg):
            v = VERB.findall(seg[:m.start()])
            v = v[-1].lower() if v else "?"
            v = "gain" if v == "gain" else "not" if v in ("don’t have", "don't have", "do not have", "lack") else "have" if v != "?" else "?"
            n = COUNT.search(seg[:m.start()])
            n = NUM[n.group(1).lower()] if n else None
            res.append((v, canon(m.group(1) or m.group(2)), int(m.group(3)) if m.group(3) else None, list(conds), n))
            if v in ("have", "not"):
                conds.append([res[-1][1], res[-1][2], v == "have"])
    return res


def split(ms):
    # a fourth element is the minimum number of parts held ("at least two parts of …")
    conds = [[s, p, v == "have"] + ([n] if n else []) for v, s, p, _, n in ms if v in ("have", "not")]
    # "If you don't have X, gain X" only guards against repeats, so it is not a condition on the gain
    gains = [[s, p, [c for c in cs if c[:2] != [s, p]]] for v, s, p, cs, _ in ms if v == "gain"]
    return conds, gains


# EN status name -> PL, voted over elements whose EN and PL mention the same number of statuses
PL_NAME = re.compile(r"„\s*([^”\"]+?)\s*[”\"]")
votes = collections.defaultdict(collections.Counter)


def vote(t_en, t_pl):
    a, b = [m[1] for m in mentions(t_en)], PL_NAME.findall(t_pl)
    if a and len(a) == len(b):
        for x, y in zip(a, b):
            votes[x][y] += 1


unknown = collections.Counter()
for eid, vid, typ in con.execute("select _id, _idVer, type from VerseElements order by _id"):
    if vid not in verses:
        continue
    v, t = verses[vid], en.get(eid, "")
    vote(t, pl.get(eid, ""))
    unknown.update(s for verb, s, *_ in mentions(t) if verb == "?")
    chs = con.execute("select _id, _idTargetVer from ChoiceInfo where _elemId=?", (eid,)).fetchall()
    if typ == 0 and not chs:
        v["text_pl"] += ("\n\n" if v["text_pl"] else "") + pl.get(eid, "")
        v["gains"] += split(mentions(t))[1]
        v["leads_pl"] += LEAD.findall(pl.get(eid, ""))
        continue
    for ch, target in chs:
        req, res = choice_txt.get((ch, EN), ("", ""))
        conds, _ = split(mentions(t) + mentions(req))
        _, gains = split(mentions(res) + mentions(req))
        vote(res, choice_txt.get((ch, PL), ("", ""))[1])
        chapter = CHAPTER.findall(t)
        heroes = sorted({h for m in HEROES.findall(t) for h in m if h})
        if "podpowied" in pl.get(eid, ""):  # "If you want to see a Hint, click here"
            v["leads_pl"].append(choice_txt.get((ch, PL), ("", ""))[1])
        v["choices"].append({
            "kind": {-1: "auto", 1: "branch", 2: "option"}.get(typ, "text"),
            "label_pl": pl.get(eid, ""), "label_en": t,
            "conds": conds, "chapter": chapter, "heroes": heroes, "gains": gains,
            "result_pl": choice_txt.get((ch, PL), ("", ""))[1],
            "target": target if target in verses else None,
        })

names = {s: c.most_common(1)[0][0] for s, c in votes.items()}
all_status = {s for v in verses.values() for s, *_ in v["gains"]} | {
    s for v in verses.values() for c in v["choices"] for s, *_ in c["conds"] + c["gains"]}
missing = sorted(all_status - names.keys())

loc_names = {n: name for i, n in loc_num.items()
             for (name,) in con.execute("select name from LocationTexts where _idLoc=? and _idLang=?", (i, PL))}
json.dump({"names_pl": names, "loc_names": loc_names, "verses": verses}, out.open("w", encoding="utf-8"), ensure_ascii=False, indent=0)

gained = {s for v in verses.values() for s, *_ in v["gains"] + [g for c in v["choices"] for g in c["gains"]]}
needed = {s for v in verses.values() for c in v["choices"] for s, *_ in c["conds"]}
print(f"{len(verses)} verses, {len(all_status)} statuses ({len(gained)} gained, {len(needed)} checked)")
print("checked but never gained:", sorted(needed - gained))
print("no Polish name:", missing)
print("mentions with no verb:", unknown.most_common(15))
