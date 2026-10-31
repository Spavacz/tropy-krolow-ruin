"""Build guide_data.json for the status guide page from statusmap.json.

Usage: python -I -X utf8 guide.py statusmap.json guide_data.json guide.html [pl|en]

The language (default pl) picks the game texts, summaries.csv or summaries_en.csv, and the page strings in ui.json.
A gate is a choice that needs a status (or a chapter, or a character) and can still lead to a status part not yet owned;
the page shows the open ones. Leads are the game's own "Nowa Wskazówka" lines, keyed to the status parts
gained right around them, so the page shows those whose thread has not moved on since.
"""
import collections
import csv
import json
import re
import sys

d = json.load(open(sys.argv[1], encoding="utf-8"))
V = {int(k): v for k, v in d["verses"].items()}
BOOKS = {999, 1001}  # entry books: reached from map locations, never walked to
LANG = sys.argv[4] if len(sys.argv) > 4 else "pl"
assert LANG in ("pl", "en"), LANG


def chapter(s):
    """'Chapter 7A: Part 3 or further' -> [num_from, num_to, letter, part, further]"""
    m = re.match(r"Chapter (\d+)(?:-(\d+))?([AB])?(?:: Part (\d+))?( or further)?", s)
    assert m, s
    a, b, letter, part, further = m.groups()
    return [int(a), int(b or a), letter or "", int(part or 0), bool(further)]


def gains_of(v):
    return [g for g in v["gains"]] + [g for c in v["choices"] for g in c["gains"]]


# status parts that may follow from a verse: walk its choices, but stop at other gates (they get their own entry)
reach_memo = {}


def reach(vid):
    seen, stack, out = set(), [vid], set()
    while stack:
        x = stack.pop()
        if x in seen or x not in V:
            continue
        seen.add(x)
        out |= {(s, p) for s, p, _ in V[x]["gains"]}
        for c in V[x]["choices"]:
            if any(h for *_, h in c["conds"]) or c["chapter"] or c["heroes"]:
                continue
            out |= {(s, p) for s, p, _ in c["gains"]}
            if c["target"]:
                stack.append(c["target"])
    return out


# map locations a book verse is entered from
parents = collections.defaultdict(set)
for vid, v in V.items():
    for c in v["choices"]:
        if c["target"]:
            parents[c["target"]].add(vid)


def entry_locs(vid):
    if V[vid]["loc"] not in BOOKS:
        return [V[vid]["loc"]]
    seen, frontier, locs = {vid}, [vid], set()
    while frontier and not locs and len(seen) < 400:
        nxt = []
        for x in frontier:
            for p in parents[x] - seen:
                seen.add(p)
                (locs.add(V[p]["loc"]) if V[p]["loc"] not in BOOKS else nxt.append(p))
        frontier = nxt
    return sorted(locs)


max_part = collections.Counter()
for v in V.values():
    for s, p, *_ in gains_of(v) + [c for ch in v["choices"] for c in ch["conds"]]:
        max_part[s] = max(max_part[s], p or 0)

gates = {}
for vid, v in V.items():
    for c in v["choices"]:
        if not (any(h for *_, h in c["conds"]) or c["chapter"] or c["heroes"]):
            continue
        r = {(s, p) for s, p, _ in c["gains"]} | (reach(c["target"]) if c["target"] else set())
        r = {g for g in r if g[1] is not None}
        if not r:
            continue
        locs = entry_locs(vid)
        if not locs:
            continue  # opened from a card (encounter, secret, chapter), not a place the party can walk to
        g = {
            "at": f'{v["loc"]}/{v["num"]}', "locs": locs,
            # a branch label is only its condition, so the page says "visit again" instead
            "label": re.sub(r"\s*\(.*", "", c["label_" + LANG]).strip() if c["kind"] == "option" else "",
            "conds": c["conds"], "chapter": [chapter(x) for x in c["chapter"]], "heroes": c["heroes"],
        }
        key = json.dumps([g["at"], g["label"], g["conds"], g["chapter"], g["heroes"]])
        g["reach"] = sorted(r | {tuple(x) for x in gates.get(key, {}).get("reach", [])})  # same choice listed per outcome
        gates[key] = g
gates = list(gates.values())

leads = []
for vid, v in V.items():
    for t in v["leads"]:
        if not t[LANG]:
            continue  # the translation has no "New Lead" line here
        # gains in the lead's verse, else in the nearest verses leading to it
        near, frontier, seen = {(s, p) for s, p, _ in gains_of(v)}, [vid], {vid}
        for _ in range(4):
            if near:
                break
            frontier = [p for x in frontier for p in parents[x] - seen]
            seen |= set(frontier)
            near = {(s, p) for x in frontier for s, p, _ in gains_of(V[x])}
        near = sorted(g for g in near if g[1] is not None)
        if near:
            leads.append({"at": f'{v["loc"]}/{v["num"]}', "text": t[LANG], "keys": near})

# leads the automatic keying misses, pinned by hand: shown once "show" is owned, until "hide" is owned
def part_key(k):
    st, p = k.split("|")
    return [st, int(p) if p else None]


# a row may also override an automatically keyed lead whose quest ends in another status; ";" separates alternatives
for r in csv.DictReader(open("leads_extra.csv", encoding="utf-8")):
    v = next(v for v in V.values() if f'{v["loc"]}/{v["num"]}' == r["at"])
    # "starts" is Polish; the element it finds gives the text in either language
    text = next(t for t in v["leads"] if t["pl"].startswith(r["starts"]))[LANG]
    leads = [l for l in leads if (l["at"], l["text"]) != (r["at"], text)]
    leads.append({"at": r["at"], "text": text, "keys": [part_key(k) for k in r["show"].split(";")],
                  "hide": [part_key(k) for k in r["hide"].split(";")]})

# one-line recaps written per status part; an empty text marks a purely mechanical part
SUMMARIES = "summaries.csv" if LANG == "pl" else f"summaries_{LANG}.csv"
try:
    summaries = {f'{r["status"]}|{r["part"]}': r["text"] for r in csv.DictReader(open(SUMMARIES, encoding="utf-8")) if r["text"]}
except FileNotFoundError:
    summaries = {}  # the page then has no "what happened" recaps; summary_src.py dumps the texts to write them from
    print(f"no {SUMMARIES}: building without summaries")


# map cards only: the entry books and chapter cards are never laid on the table
loc_names = {n: name for n, name in d["loc_names"].items() if int(n) not in BOOKS and int(n) < 1100}
shown_names = loc_names if LANG == "pl" else {n: d["loc_names_en"].get(n, nm) for n, nm in loc_names.items()}


def name_pattern(name):
    # Polish inflects place names ("Colonii Mariana", "Latyfundiów"), so match each word by its stem; it fits English plurals too
    words = re.findall(r"\w+", name.split(",")[0])
    return re.compile(r"\b" + r"\s+".join(re.escape(w[:max(4, len(w) - 2)]) + r"\w*" for w in words) + r"\b", re.I)


# where each lead is read and where it points, so the page can drop hints about regions no longer on the table
at_vid = {f'{v["loc"]}/{v["num"]}': vid for vid, v in V.items()}
place_names = {int(n): name_pattern(nm) for n, nm in shown_names.items()}
for l in leads:
    targets = {int(x) for x in re.findall(r"\(\s*(\d{3})\s*\)", l["text"]) if x in loc_names}
    targets |= {n for n, p in place_names.items() if p.search(l["text"])}
    l["locs"] = sorted(set(entry_locs(at_vid[l["at"]])) | targets)

# where each summarized part is granted, so the player can reread it in the app (texts stay in the app)
sources = collections.defaultdict(list)
for v in V.values():
    at = f'{v["loc"]}/{v["num"]}'
    for st, p, _ in v["gains"] + [g for c in v["choices"] for g in c["gains"]]:
        if f"{st}|{p}" in summaries and at not in sources[f"{st}|{p}"]:
            sources[f"{st}|{p}"].append(at)

# entries that close a chapter part: they send the party to "Rozdział 7B: Część 3", or end a whole chapter
chapter_texts = collections.defaultdict(list)
for v in V.values():
    text = "\n\n".join([v["text_pl"]] + [c["result_pl"] for c in v["choices"] if c["result_pl"]])
    keys = {f"{a}:{b}" for a, b in re.findall(r"kart[eęy]\s+Rozdział\w*\s+(\d+[AB]?)\s*:\s*Część\s*(\d+)", text)}
    keys |= {f"END {a}" for a in re.findall(r"ukończyć Rozdział\s+(\d+[AB]?)", text)}
    for k in sorted(keys):  # sets iterate in a per-run order; keep the output byte-stable
        chapter_texts[k].append(f'{v["loc"]}/{v["num"]}')

out = {"names": d["names_pl"] if LANG == "pl" else {}, "loc_names": shown_names, "max_part": max_part, "gates": gates, "leads": leads, "summaries": summaries, "sources": sources, "chapter_refs": chapter_texts}
data = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
open(sys.argv[2], "w", encoding="utf-8").write(data)
page = open("guide_template.html", encoding="utf-8").read()
logic = open("guide_logic.js", encoding="utf-8").read()
# page strings: {{key}} in the template, from ui.json {key: {pl, en}}; a missing key or language fails the build
ui = json.load(open("ui.json", encoding="utf-8"))
page = re.sub(r"\{\{(\w+)\}\}", lambda m: ui[m[1]][LANG], page)
open(sys.argv[3], "w", encoding="utf-8").write(page.replace("/*DATA*/", data).replace("/*LOGIC*/", logic))
print(f"{len(gates)} gates, {len(leads)} of {sum(len(v['leads']) for v in V.values())} leads keyed ({LANG})")
