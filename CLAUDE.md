# Tropy Królów Ruin

Odpowiadaj użytkownikowi po polsku. To strona bez spoilerów do gry planszowej Tainted Grail: Królowie Ruin
(aplikacja Companion, kampania 26). Gracz zaznacza statusy z papierowego arkusza, a strona pokazuje, co się
działo i dokąd iść. Jest hostowana na Netlify: https://tropy-krolow-ruin.netlify.app (instalowalna jako aplikacja).

Siostrzany projekt to polski lektor w `C:\Workspace\tgrail`. W jego katalogu leżą dane z telefonu,
z których korzysta też ta strona.

## Dane źródłowe (nie są w repo)

Jedynym wejściem jest `appData.sqlite` z aplikacji (75 MB, wszystkie teksty gry). Leży w katalogu repo,
ale jest w `.gitignore`. Na telefonie leży w
`/sdcard/Android/data/com.AwakenRealms.TaintedGrail/files/AppContent/appData.sqlite`, a `README.md` opisuje
krok po kroku, jak ją pobrać (adb, `MSYS_NO_PATHCONV=1` w Git Bash). adb jest w
`/c/Users/spavm/AppData/Local/Microsoft/WinGet/Packages/Google.PlatformTools_*/platform-tools/` i nie jest
na PATH. Nagrania nie są tu potrzebne. Treść gry jest chroniona, dlatego
baza i pliki z pełnym tekstem (`statusmap.json`, `guide_data*.json`) są w `.gitignore`, a w repo są tylko
gotowe `guide.html` i `guide_<kod>.html` (krótkie cytaty, streszczenia, numery wpisów). Generowanie jest deterministyczne:
przebudowa z tej samej bazy daje identyczne strony.

Schemat bazy, który się przydaje: `Location` (`_campId=26`, `displayNumber`), `Verse` (wersy lokacji),
`VerseElements` (typ: 0 narracja, 1 warunek, 2 opcja, -1 warunek automatyczny), `ElemetText` (sic),
`ChoiceInfo` (cel: `_idTargetLoc`/`_idTargetVer` to wewnętrzne `_id`, nie numery z gry), `ChoiceInfoText`
(`reqTxt`, `resTxt`), `LocationTexts` (nazwy lokacji). Język: 1 EN, 2 PL. **999 i 1001 to jedna Księga
Tajemnic** (KT): 999 to wpisy 0–600, 1001 to wpisy 601–1263; „999/503” w grze to „KT wpis 503”.
1101+ to karty rozdziałów i samouczek, a nie lokacje na mapie.

## Potok

Skrypty używają tylko biblioteki standardowej Pythona. Testy wymagają `node`.

```
python -I -X utf8 statusmap.py appData.sqlite statusmap.json
python -I -X utf8 guide.py statusmap.json          # wszystkie języki z lang/, albo: ... statusmap.json en de
node guide_test.js guide_data.json                 # i guide_data_<kod>.json dla pozostałych
```

- `statusmap.py` parsuje **angielski** tekst (ma regularne sformułowania: „Gain the “X” part N status”,
  „If you have…”, „requires…”, „at least two parts of…”, postaci, rozdziały). Polskie nazwy i etykiety
  są podpinane po tym samym elemencie. W tekstach gry są literówki i mieszane cudzysłowy (“” " '), które
  obsługuje `ALIAS`/`canon`.
- `guide.py` buduje bramki (wybory wymagające statusu, rozdziału albo postaci, które prowadzą do jeszcze
  niezdobytej części), wskazówki („Nowa Wskazówka” i przyciski „Podpowiedź”), streszczenia, odnośniki do
  wpisów i wstawia dane z logiką do `guide_template.html`, co daje samodzielny `guide.html`.
- Każdy język to osobna strona: polski `guide.html` (Netlify `/`), reszta `guide_<kod>.html`, wszystkie w repo
  i na Netlify (decyzja użytkownika). Przełącznik w nagłówku linkuje strony; stan w `localStorage` jest wspólny.
  Wybrany język jest zapamiętany (`tropy-kr-lang`); samo `/` przekierowuje na niego, `/guide.html` już nie. Napisy strony są w `lang/<kod>/ui.json` (`{{klucz}}` w szablonie, w HTML
  i w literałach JS, więc teksty bez `"` i `` ` ``). `statusmap.json` trzyma teksty gry we wszystkich językach kampanii (en, pl, fr, es, de, it, ru, cn).
  Znacznik „New Lead” każdego tłumaczenia jest wykrywany sam (najczęstsze pogrubienie przy angielskim „New Lead”).
  Testy dopasowują po miejscu i warunku, nie po etykiecie, żeby działały w każdym języku.
- `guide_logic.js` to logika współdzielona przez stronę i testy: warunki, rozdziały, liczniki, wskazówki,
  kodowanie stanu do linku. `guide_test.js` zawiera testy na prawdziwych danych.
- Publikacja: Netlify z repo GitHub (`netlify.toml`: bez kroku budowania, `/` serwuje `guide.html`), więc
  wystarczy commit i push gotowych `guide*.html`. `PAGE_URL` w szablonie bierze adres strony z `location`.
  Artefakt claude.ai został usunięty; ramka artefaktu dawała domyślne style (viewport, `[hidden]`, margines
  `body`), które strona ma teraz sama.

## Dane pisane ręcznie (reszta jest generowana)

- `lang/pl/summaries.csv`: streszczenia każdej części statusu (`status` po angielsku, `part`, tekst po polsku;
  pusty tekst oznacza część czysto mechaniczną). Styl: 1–2 zdania, **formy neutralne płciowo** (bez
  „-łeś/-łaś”), tylko to, co już się wydarzyło. Brakujące części po zmianie danych wypisze
  `summary_src.py statusmap.json <katalog> 40`. Inny język ma własny plik (`lang/<kod>/summaries.csv`, z
  `summary_src.py … 40 <kod>`), pisany z tekstu gry w tym języku, a nie tłumaczony. Są `pl` i `en` (en pisane z angielskiego tekstu gry).
  Pliki ręczne leżą w `lang/<kod>/`; brakujący plik guide.py bierze z `lang/pl/`, poza streszczeniami.
  Każdy język kampanii ma `lang/<kod>/ui.json` (tłumaczenia napisów strony); build odrzuca w nich " ' ` \ < >.
- `lang/pl/leads_extra.csv`: wskazówki z ręcznie dobranym warunkiem pokazania (`show`) i zniknięcia (`hide`),
  alternatywy oddzielone `;`. Wiersz nadpisuje też automatycznie przypiętą wskazówkę. Używaj, gdy
  zadanie kończy się statusem z innego wątku, np. mapa senatora kończy się na Przyjaciel szlachty cz. 3.

## Decyzje użytkownika, których należy się trzymać

- Rady **bez spoilerów**: nazwa opcji z gry i powód („masz X cz. N”), nigdy co się stanie.
- **Nie osadzać tekstów z gry** na stronie, tylko numery wpisów („lokacja 155, wers 8”, „KT wpis 503”).
  Krótkie cytaty (treść wskazówek, nazwy opcji i lokacji) zostają.
- Strona startuje **pusta**. Stan jest zapisany w `localStorage`. Link `#t<wersja>-<base36>` przenosi stan
  i wczytuje się sam, gdy nic nie jest zaznaczone, a w przeciwnym razie pyta. Wersja to skrót układu statusów i lokacji, więc przebudowa danych z nowymi
  statusami unieważnia stare linki (strona to zgłasza).
- Mapa: gracz zaznacza lokacje leżące na stole. Rady i wskazówki są filtrowane po miejscu, w którym
  padły, **i** po miejscach, do których prowadzą (numery i odmienione nazwy w tekście).
- „Co się działo”: na wierzchu tylko wątki, które coś teraz otwierają na mapie albo trzymają aktywną
  wskazówkę. Reszta jest w zwiniętej sekcji „Starsze wątki”.
- Wybory otwierane z kart (Spotkania, Sekrety, Rozdziały) nie są radami „dokąd iść”, więc są pomijane.

## Znane ograniczenia

Strona nie zna stanu planszy (znaczniki, Forma Dziwu, „Isolut w grze”). Strony „b” lokacji mają numer
lokacji podstawowej. Kolejność zdobywania statusów nie jest znana, więc „ostatnio” oznacza „ważne teraz”.
