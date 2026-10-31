# Tropy Królów Ruin

A spoiler-free companion page for the Kings of Ruin campaign of Tainted Grail. You tick the statuses from your
paper campaign sheet, and the page shows what has happened so far and where to go next. The Polish build is online
at https://tropy-krolow-ruin.netlify.app

The ready Polish page is `guide.html`; it also works opened straight from disk. Rebuilding it, or building it in
another language, needs the game's text database, which is not in the repo because it is the game's protected
content.

## Getting the game database

The only missing file is `appData.sqlite` (about 75 MB), the text database of the official Tainted Grail Companion
app (`com.AwakenRealms.TaintedGrail`). `statusmap.json` and `guide_data.json` are built from it.

1. Install the app on an Android phone and open it once so it downloads the campaign content.
2. Turn on USB debugging (Developer options) and connect the phone to the computer.
3. Install adb, on Windows e.g. `winget install Google.PlatformTools`.
4. In the repo folder run:

   ```
   adb pull /sdcard/Android/data/com.AwakenRealms.TaintedGrail/files/AppContent/appData.sqlite .
   ```

   In Git Bash on Windows, run `export MSYS_NO_PATHCONV=1` first, or the path gets rewritten into a Windows one.

Pull the database again after any app update that changes the texts.

## Building

Needs Python 3 (standard library only) and Node.js for the tests:

```
python -I -X utf8 statusmap.py appData.sqlite statusmap.json
python -I -X utf8 guide.py statusmap.json guide_data.json guide.html
node guide_test.js guide_data.json
```

## Building in another language

The last argument of `guide.py` picks the page language; the default is `pl`:

```
python -I -X utf8 guide.py statusmap.json guide_data.json guide.html en
```

The language code is the one the app's database uses. The campaign is translated into `en`, `pl`, `fr`, `es`,
`de`, `it`, `ru` and `cn`; `statusmap.py` prints the list it found.

The hand-written files of each language sit in their own folder, `lang/<code>/`. To add a language, create its
folder; the build reads it when that language is chosen. A file the folder lacks is read from `lang/pl/`, the
complete default, except `summaries.csv` (see below). Each part of the page comes from its own place:

- **Game texts** (option names, location and status names, the game's "New Lead" hints) come from the database in
  the chosen language, so there is nothing to write. A status name the translation does not quote recognisably stays
  in English; French, which marks names in bold instead of quotes, keeps many of them in English.
- **Page strings** (headings, buttons, messages) come from `lang/<code>/ui.json`, a `{key: text}` map. Copy
  `lang/en/ui.json` and translate the values. A missing key is taken from `lang/pl/ui.json`, and the build lists
  such keys. The strings go into HTML and JavaScript literals, so they must not contain `"` or a backtick. Set
  `lang` to the page's BCP 47 language tag (e.g. `de`), which also drives alphabetical sorting.
- **Summaries** ("what has happened", one or two sentences per status part) are written by hand in
  `lang/<code>/summaries.csv`, with the columns of `lang/pl/summaries.csv` (`status` in English, `part`, `text`;
  an empty `text` marks a purely mechanical part). This file is never borrowed from another language: without it
  the page is built without that section. To write one, dump the game text where each part is gained, in batches:

  ```
  python -I -X utf8 summary_src.py statusmap.json <folder> 40 de
  ```

  Write each summary from the game text in that language rather than translating the Polish file; the translations
  differ in detail. Keep to what has already happened, without hinting at what comes next.
- **Pinned hints** (`leads_extra.csv`, hints shown from and hidden by hand-picked statuses) work for every language
  from `lang/pl/`: a row finds the hint by the start of its Polish text and shows it in the chosen language.

The build has no step for publishing; host the resulting `guide.html` wherever you like.

Further details and the project's rules are in `CLAUDE.md`.
