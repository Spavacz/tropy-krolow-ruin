"""Build statusmap.json: the Kings of Ruin verse graph with every status gain and status condition.

Usage: python -I -X utf8 statusmap.py appData.sqlite statusmap.json

English text is parsed (its wording is regular); Polish labels and status names ride along by element.
"""
import collections
import itertools
import json
import re
import sqlite3
import sys
from pathlib import Path

CAMP, EN, PL = 26, 1, 2
SKIP = {"tst"}  # the app's test language

db, out = Path(sys.argv[1]), Path(sys.argv[2])
con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)


FR = 7
# French marks a status name in bold ("le statut <b>Topographie</b>"), not in quotes: quote it before the tags go,
# so the name vote below can pair it with the English one
BOLD_NAME = re.compile(r"(statuts?\s*(?:</?b>\s*)*)<b>\s*([^<]+?)\s*</b>")


def clean(t, lang=None):
    if lang == FR:
        t = BOLD_NAME.sub(r"\1« \2 »", t or "")
    t = re.sub(r"<[^>]*>|@\w+@", " ", t or "")
    t = re.sub(r"\s*\((Chapter [^)]*)\)\s*”", r": \1”", t)  # keep "(" inside a status name from splitting clauses
    t = t.replace("''", "”")  # one text closes a status name with two apostrophes
    return re.sub(r"\s+", " ", t).strip()


def texts(lang):
    return {e: clean(t, lang) for e, t in con.execute("select _idElem, text from ElemetText where _idLang=?", (lang,))}


# every language the app ships text for, by its code in the Languages table (en, pl, de, fr, ...)
LANGS = {code: i for i, _, code, *_ in con.execute("select * from Languages")
         if code not in SKIP and con.execute(  # some translations (cz, kr) lack this campaign altogether
             "select 1 from LocationTexts t join Location l on l._id=t._idLoc where l._campId=? and t._idLang=? limit 1",
             (CAMP, i)).fetchone()}
T = {code: texts(i) for code, i in LANGS.items()}
en, pl = T["en"], T["pl"]
choice_txt = {(ch, lang): (clean(r, lang), clean(s, lang)) for ch, lang, r, s in con.execute(
    "select _idChoice, _idLang, reqTxt, resTxt from ChoiceInfoText")}

loc_num = dict(con.execute("select _id, displayNumber from Location where _campId=?", (CAMP,)))
verses = {vid: {"loc": loc_num[l], "num": n, **{"text_" + c: "" for c in LANGS}, "leads": [], "gains": [], "choices": []}
          for vid, l, n in con.execute("select _id, _locationId, displayNumber from Verse") if l in loc_num}

ALIAS = {"s mall favor": "Small Favor", "small favors": "Small Favor", "times passes": "Time Passes"}  # typos in the source texts
STATUS = re.compile(r"(?:[“\"]\s*([^“”\"]{1,40}?)\s*[”\"]|(?<!\w)'\s*([^'“”\"]{1,40}?)\s*')(?:\s*part\s*(\d+))?\s*status")
COUNT = re.compile(r"at least (\w+) parts? of the\s*$", re.I)  # "at least two parts of the “X” status"
NUM = {w: i for i, w in enumerate("zero one two three four five six seven eight nine ten".split())}
HERO = r"(Elgan|Gerdwyn|Iunis|Osbert)"
# "requires Elgan or Gerdwyn", "If you're playing Iunis", "If Osbert is in this Location"
HEROES = re.compile(rf"(?:requires|playing|[Ii]f)\s+{HERO}(?:\s*(?:,\s*|\s+or\s+){HERO})?(?:\s+or\s+{HERO})?")
VERB = re.compile(r"\b(gain|don’t have|don't have|do not have|lack|have|requires?)\b", re.I)
LEAD_EN = re.compile(r"New Lead:\s*(.+)", re.I)  # the game's own spoiler-free pointers
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


def lead_mark(code):
    """Each translation names "New Lead" in its own words, in bold; take the bold phrase most common in the
    elements whose English has one ("Nowa Wskazówka", "Neue Spur", "新线索")."""
    seen = collections.Counter()
    for e in (e for e, t in en.items() if LEAD_EN.search(t)):
        for (raw,) in con.execute("select text from ElemetText where _idElem=? and _idLang=?", (e, LANGS[code])):
            seen.update({m.strip(" :：") for m in re.findall(r"<b>([^<]{2,40}?)</b>", raw or "")} - {""})
    return seen.most_common(1)[0][0] if seen else None  # a partial translation may have no lead texts


MARK = {code: lead_mark(code) for code in LANGS}
LEAD = {code: re.compile(re.escape(m or "(no lead mark)") + r"\s*[:：]\s*(.+)", re.I) for code, m in MARK.items()}

# EN status name -> translated name, voted over elements whose EN and translation mention the same number of statuses
QUOTED = {"pl": re.compile(r"„\s*([^”\"]+?)\s*[”\"]")}
ANY_QUOTE = re.compile(r"[„“«‹「『\"]\s*([^„“”«»‹›「」『』\"]+?)\s*[”“»›」』\"]")  # quote styles of the other translations
votes = {code: collections.defaultdict(collections.Counter) for code in LANGS if code != "en"}


def vote(t_en, tr):
    a = [m[1] for m in mentions(t_en)]
    for code, t in tr.items():
        b = QUOTED.get(code, ANY_QUOTE).findall(t)
        if code in votes and a and len(a) == len(b):
            for x, y in zip(a, b):
                votes[code][x][y] += 1


unknown = collections.Counter()
for eid, vid, typ in con.execute("select _id, _idVer, type from VerseElements order by _id"):
    if vid not in verses:
        continue
    v, t = verses[vid], en.get(eid, "")
    vote(t, {code: T[code].get(eid, "") for code in LANGS})
    unknown.update(s for verb, s, *_ in mentions(t) if verb == "?")
    chs = con.execute("select _id, _idTargetVer from ChoiceInfo where _elemId=?", (eid,)).fetchall()
    if typ == 0 and not chs:
        for code in LANGS:
            v["text_" + code] += ("\n\n" if v["text_" + code] else "") + T[code].get(eid, "")
        v["gains"] += split(mentions(t))[1]
        # paired by element; a lead a translation lacks stays "" there and is left out of that language's page
        found = [LEAD[code].findall(T[code].get(eid, "")) for code in LANGS]
        v["leads"] += [dict(zip(LANGS, row)) for row in itertools.zip_longest(*found, fillvalue="")]
        continue
    for ch, target in chs:
        req, res = choice_txt.get((ch, EN), ("", ""))
        result = {code: choice_txt.get((ch, i), ("", ""))[1] for code, i in LANGS.items()}
        conds, _ = split(mentions(t) + mentions(req))
        _, gains = split(mentions(res) + mentions(req))
        vote(res, result)
        chapter = CHAPTER.findall(t)
        heroes = sorted({h for m in HEROES.findall(t) for h in m if h})
        # the Polish wording marks a hint choice ("Podążaj za podpowiedziami Orrina"); the English varies
        if "podpowied" in pl.get(eid, ""):
            v["leads"].append(result)
        v["choices"].append({
            "kind": {-1: "auto", 1: "branch", 2: "option"}.get(typ, "text"),
            **{"label_" + code: T[code].get(eid, "") for code in LANGS},
            "conds": conds, "chapter": chapter, "heroes": heroes, "gains": gains,
            **{"result_" + code: r for code, r in result.items()},
            "target": target if target in verses else None,
        })

names = {code: {s: c.most_common(1)[0][0] for s, c in vs.items()} for code, vs in votes.items()}
all_status = {s for v in verses.values() for s, *_ in v["gains"]} | {
    s for v in verses.values() for c in v["choices"] for s, *_ in c["conds"] + c["gains"]}


def loc_names(lang):
    return {n: name for i, n in loc_num.items()
            for (name,) in con.execute("select name from LocationTexts where _idLoc=? and _idLang=?", (i, lang))}


json.dump({"langs": list(LANGS), "names": names, "loc_names": {code: loc_names(i) for code, i in LANGS.items()},
           "verses": verses}, out.open("w", encoding="utf-8"), ensure_ascii=False, indent=0)

gained = {s for v in verses.values() for s, *_ in v["gains"] + [g for c in v["choices"] for g in c["gains"]]}
needed = {s for v in verses.values() for c in v["choices"] for s, *_ in c["conds"]}
print(f"{len(verses)} verses, {len(all_status)} statuses ({len(gained)} gained, {len(needed)} checked)")
print("checked but never gained:", sorted(needed - gained))
print("languages:", ", ".join(LANGS), "| lead marks:", MARK)
for code, ns in names.items():
    if all_status - ns.keys():
        print(f"no {code} name:", sorted(all_status - ns.keys()))
print("mentions with no verb:", unknown.most_common(15))
