"""Dump, per status part, the game text where it is gained, in batches for writing summaries.csv (or summaries_en.csv).

Usage: python -I -X utf8 summary_src.py statusmap.json OUT_DIR [BATCH_SIZE] [pl|en]
Parts already in that language's summaries file are skipped. Write each language from its own game text, not by
translating the other file: the translations differ in detail.
"""
import collections
import csv
import json
import sys
from pathlib import Path

d = json.load(open(sys.argv[1], encoding="utf-8"))
out, size = Path(sys.argv[2]), int(sys.argv[3]) if len(sys.argv) > 3 else 40
lang = sys.argv[4] if len(sys.argv) > 4 else "pl"
summaries = Path("summaries.csv" if lang == "pl" else f"summaries_{lang}.csv")
V = {int(k): v for k, v in d["verses"].items()}
done = set()
if summaries.exists():
    done = {(r["status"], int(r["part"])) for r in csv.DictReader(open(summaries, encoding="utf-8"))}

into = collections.defaultdict(list)  # verse -> labels of choices leading to it
for v in V.values():
    for c in v["choices"]:
        if c["target"] and c["label_" + lang]:
            into[c["target"]].append(c["label_" + lang])

src = collections.defaultdict(list)
for vid, v in V.items():
    head = f'[{v["loc"]}/{v["num"]}] ' + " | ".join(dict.fromkeys(into[vid]))[:200]
    for s, p, _ in v["gains"]:
        src[(s, p)].append(f'{head}\n{v["text_" + lang][:600]}')
    for c in v["choices"]:
        for s, p, _ in c["gains"]:
            src[(s, p)].append(f'{head}\n{v["text_" + lang][:450]}\n> {c["label_" + lang][:200]}\n{c["result_" + lang][:400]}')

todo = sorted(k for k in src if k[1] is not None and k not in done)
out.mkdir(parents=True, exist_ok=True)
for i in range(0, len(todo), size):
    with open(out / f"batch{i // size + 1:02}.txt", "w", encoding="utf-8") as f:
        for s, p in todo[i:i + size]:
            f.write(f"\n##### {s} | {p} | {d['names'].get(lang, {}).get(s, s)}\n")
            f.write("\n---\n".join(src[(s, p)][:2]) + "\n")
print(len(todo), "parts to summarize in", -(-len(todo) // size), "batches")
