# Tropy Królów Ruin

Strona bez spoilerów do kampanii „Królowie Ruin” gry Tainted Grail. Zaznaczasz statusy z papierowego arkusza,
a strona pokazuje, co się działo i dokąd iść. Wersja online: https://tropy-krolow-ruin.netlify.app

Gotowa strona to `guide.html`. Działa też po otwarciu z dysku. Do przebudowy potrzebna jest baza tekstów gry,
której nie ma w repo, bo to chroniona treść gry.

## Skąd wziąć brakujące pliki

Jedyny brakujący plik to `appData.sqlite` (ok. 75 MB), czyli baza tekstów oficjalnej aplikacji
Tainted Grail Companion (`com.AwakenRealms.TaintedGrail`). Pliki `statusmap.json` i `guide_data.json`
powstają z niej przy budowaniu.

1. Na telefonie z Androidem zainstaluj aplikację i otwórz ją raz, żeby pobrała zawartość kampanii.
2. Włącz debugowanie USB (Opcje programisty) i podłącz telefon do komputera.
3. Zainstaluj adb, na Windows np. `winget install Google.PlatformTools`.
4. W katalogu repo uruchom:

   ```
   adb pull /sdcard/Android/data/com.AwakenRealms.TaintedGrail/files/AppContent/appData.sqlite .
   ```

   W Git Bash na Windows poprzedź to `export MSYS_NO_PATHCONV=1`, bo inaczej ścieżka zostanie przerobiona
   na windowsową.

Bazę trzeba pobrać ponownie po każdej aktualizacji aplikacji, która zmienia teksty.

## Budowanie

Wymaga Pythona 3 (tylko biblioteka standardowa) i Node.js do testów:

```
python -I -X utf8 statusmap.py appData.sqlite statusmap.json
python -I -X utf8 guide.py statusmap.json guide_data.json guide.html
node guide_test.js guide_data.json
```

Ostatni argument `guide.py` wybiera język strony: `pl` (domyślny) albo `en`, np.
`python -I -X utf8 guide.py statusmap.json guide_data.json guide.html en`. Teksty z gry (nazwy opcji, lokacji,
statusów, wskazówki) idą z bazy w wybranym języku, napisy strony z `ui.json`, a streszczenia z `summaries.csv`
(pl) albo `summaries_en.csv` (en). Bez pliku streszczeń strona buduje się bez sekcji „Co się działo”.

Szczegóły działania i zasady rozwoju są w `CLAUDE.md`.
