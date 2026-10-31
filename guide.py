"""Build the status guide pages from statusmap.json, one per language.

Usage: python -I -X utf8 guide.py statusmap.json [LANG ...]

Each LANG is a language code of the app's database with a folder lang/<LANG>/ of hand-written files (ui.json,
summaries.csv, leads_extra.csv); without arguments every such language is built. English, the default, goes to
guide.html and guide_data.json, any other language to guide_<LANG>.html and guide_data_<LANG>.json. Every page links
to all languages with a folder. A file a folder lacks is read from lang/en/; for summaries.csv that means a page
without its own recaps shows the English ones rather than none.
A gate is a choice that needs a status (or a chapter, or a character) and can still lead to a status part not yet owned;
the page shows the open ones. Leads are the game's own "New Lead" lines, keyed to the status parts
gained right around them, so the page shows those whose thread has not moved on since.
"""
import collections
import csv
import json
import re
import sys
from pathlib import Path

d = json.load(open(sys.argv[1], encoding="utf-8"))
V = {int(k): v for k, v in d["verses"].items()}
BOOKS = {999, 1001}  # entry books: reached from map locations, never walked to
DEFAULT = "en"  # the complete folder, and the page Netlify serves at /
ALL = [c for c in d["langs"] if Path("lang", c).is_dir()]
assert DEFAULT in ALL, ALL


def page_name(lang):
    return "guide.html" if lang == DEFAULT else f"guide_{lang}.html"


def manifest_name(lang):
    return "manifest.webmanifest" if lang == DEFAULT else f"manifest_{lang}.webmanifest"


def data_name(lang):
    return "guide_data.json" if lang == DEFAULT else f"guide_data_{lang}.json"


def lang_file(lang, name):
    own = Path("lang", lang, name)
    if own.exists():
        return own
    print(f"no {own.as_posix()}: using lang/{DEFAULT}/{name}")
    return Path("lang", DEFAULT, name)


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

# map cards only: the entry books and chapter cards are never laid on the table
loc_names = {n: name for n, name in d["loc_names"]["pl"].items() if int(n) not in BOOKS and int(n) < 1100}


def name_pattern(name):
    # Polish inflects place names ("Colonii Mariana", "Latyfundiów"), so match each word by its stem; it fits English plurals too
    words = re.findall(r"\w+", name.split(",")[0])
    return re.compile(r"\b" + r"\s+".join(re.escape(w[:max(4, len(w) - 2)]) + r"\w*" for w in words) + r"\b", re.I)


# entries that close a chapter part: they send the party to "Rozdział 7B: Część 3", or end a whole chapter;
# read from the Polish text, which every database has, and the keys hold no text, so this serves every language
chapter_texts = collections.defaultdict(list)
for v in V.values():
    text = "\n\n".join([v["text_pl"]] + [c["result_pl"] for c in v["choices"] if c["result_pl"]])
    keys = {f"{a}:{b}" for a, b in re.findall(r"kart[eęy]\s+Rozdział\w*\s+(\d+[AB]?)\s*:\s*Część\s*(\d+)", text)}
    keys |= {f"END {a}" for a in re.findall(r"ukończyć Rozdział\s+(\d+[AB]?)", text)}
    for k in sorted(keys):  # sets iterate in a per-run order; keep the output byte-stable
        chapter_texts[k].append(f'{v["loc"]}/{v["num"]}')


def build(LANG):
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
    extra = lang_file(LANG, "leads_extra.csv")
    for r in csv.DictReader(open(extra, encoding="utf-8")):
        v = next(v for v in V.values() if f'{v["loc"]}/{v["num"]}' == r["at"])
        # "starts" is in the language of the folder the file came from; the lead it finds has every language
        text = next(t for t in v["leads"] if t[extra.parent.name].startswith(r["starts"]))[LANG]
        leads = [l for l in leads if (l["at"], l["text"]) != (r["at"], text)]
        leads.append({"at": r["at"], "text": text, "keys": [part_key(k) for k in r["show"].split(";")],
                      "hide": [part_key(k) for k in r["hide"].split(";")]})

    # one-line recaps written per status part; an empty text marks a purely mechanical part
    SUMMARIES = lang_file(LANG, "summaries.csv")
    try:
        summaries = {f'{r["status"]}|{r["part"]}': r["text"] for r in csv.DictReader(open(SUMMARIES, encoding="utf-8")) if r["text"]}
    except FileNotFoundError:
        summaries = {}  # the page then has no "what happened" recaps; summary_src.py dumps the texts to write them from
        print(f"no {SUMMARIES.as_posix()}: building without summaries")


    shown_names = {n: d["loc_names"][LANG].get(n, nm) for n, nm in loc_names.items()}

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

    out = {"names": d["names"].get(LANG, {}), "loc_names": shown_names, "max_part": max_part, "gates": gates, "leads": leads, "summaries": summaries, "sources": sources, "chapter_refs": chapter_texts}
    data = json.dumps(out, ensure_ascii=False, separators=(",", ":"))
    open(data_name(LANG), "w", encoding="utf-8").write(data)
    page = open("guide_template.html", encoding="utf-8").read()
    logic = open("guide_logic.js", encoding="utf-8").read()
    # page strings: {{key}} in the template, from ui.json {key: text}; a key the language lacks comes from the default
    ui = json.load(open(Path("lang", DEFAULT, "ui.json"), encoding="utf-8"))
    own = json.load(open(lang_file(LANG, "ui.json"), encoding="utf-8"))
    if ui.keys() - own.keys():
        print(f"page strings missing from lang/{LANG}/ui.json, {DEFAULT} used:", ", ".join(sorted(ui.keys() - own.keys())))
    ui.update(own)
    # the strings land in HTML and in "…", '…' and `…` JavaScript literals unescaped
    bad = {k: t for k, t in ui.items() if re.search(r"[\"'`\\<>]", t)}
    assert not bad, f"lang/{LANG}/ui.json strings must not contain \" ' ` \\ < >: {bad}"
    # the language switch: every language's own name, linking to its page
    ui["manifest"] = manifest_name(LANG)
    ui["lang_options"] = "".join(f'<option value="{page_name(c)}" data-lang="{TAGS[c]}"{" selected" if c == LANG else ""}>{NAMES[c]}</option>' for c in ALL)
    page = re.sub(r"\{\{(\w+)\}\}", lambda m: ui[m[1]], page)
    # each language installs as its own app, named in that language and opening on its page
    manifest = {"name": ui["title"], "short_name": ui["short_name"], "description": ui["tagline"], "lang": ui["lang"],
                "start_url": "/" if LANG == DEFAULT else "/" + page_name(LANG), "scope": "/", "display": "standalone",
                "background_color": "#eef0ea", "theme_color": "#2f6b5a",
                "icons": [{"src": f"/icon-{n}.png", "sizes": f"{n}x{n}", "type": "image/png", "purpose": "any maskable"} for n in (192, 512)]}
    with open(manifest_name(LANG), "w", encoding="utf-8", newline="\n") as f:
        json.dump(manifest, f, ensure_ascii=False, indent=2)
        f.write("\n")
    open(page_name(LANG), "w", encoding="utf-8").write(page.replace("/*DATA*/", data).replace("/*LOGIC*/", logic))
    print(f"{len(gates)} gates, {len(leads)} of {sum(len(v['leads']) for v in V.values())} leads keyed ({LANG})")


UI = {c: json.load(open(lang_file(c, "ui.json"), encoding="utf-8")) for c in ALL}
NAMES = {c: u["lang_name"] for c, u in UI.items()}
TAGS = {c: u["lang"] for c, u in UI.items()}  # BCP 47, matched against the browser's languages
for lang in sys.argv[2:] or ALL:
    assert lang in ALL, f"{lang} has no lang/{lang}/ folder or no text in the database; languages: {ALL}"
    build(lang)
