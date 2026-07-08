# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Język

Użytkownik jest Polakiem. Komunikacja, komentarze w kodzie, komunikaty commitów, README i UI dashboardu — po polsku. Komunikaty logów w `tracker.py` celowo bez polskich znaków (ASCII), bo trafiają do logów Actions.

## Czym jest ten projekt

Tracker najniższych cen produktów rowerowych w Europie kontynentalnej. Działa jako GitHub Actions (cron `23 10 * * *` UTC = 12:23 CEST; nieokrągła minuta celowo — crony `:00` bywają pomijane przez GitHub). Bot commituje wyniki do repo. Nie ma serwera — dashboard to statyczny HTML z osadzonymi danymi, gadający z GitHub API tokenem z localStorage przeglądarki.

## Komendy

System Python jest externally-managed (PEP 668) — używaj venv:

```bash
python3 -m venv /tmp/pt-venv && /tmp/pt-venv/bin/pip install -r requirements.txt
```

Nie ma test suite. Weryfikacja zmian:

```bash
# 1. kompilacja
/tmp/pt-venv/bin/python -m py_compile tracker.py dashboard.py

# 2. składnia JS z szablonu dashboardu (największy blok <script>)
/tmp/pt-venv/bin/python -c "
import re, pathlib
tpl = pathlib.Path('dashboard.py').read_text()
js = max(re.findall(r'<script>\n(.*?)</script>', tpl, re.S), key=len)
pathlib.Path('/tmp/dash.js').write_text(js)" && node --check /tmp/dash.js

# 3. lokalna regeneracja dashboardu (output/dashboard.html + docs/index.html)
/tmp/pt-venv/bin/python -c "
import csv, yaml
from datetime import date
from dashboard import build_dashboard
cfg = yaml.safe_load(open('products.yaml'))
rows = list(csv.DictReader(open('data/history.csv')))
print(build_dashboard(rows, cfg['products'], cfg.get('settings') or {}, date.today().isoformat()))"
```

Pełny run lokalny: `python tracker.py` (bez kluczy w env pomija discovery i sprawdza tylko znane URL-e — bezpieczne). Klucze: `SERPAPI_KEY`, opcjonalnie `TAVILY_API_KEY`, `BRAVE_API_KEY`. `SKIP_DISCOVERY=1` wymusza tryb Light FIRE (zero zapytań do wyszukiwarek).

`gh` CLI nie jest zainstalowane. Do GitHub API używaj tokenu z git credential helper:

```bash
creds=$(printf "protocol=https\nhost=github.com\n" | git credential fill)
TOKEN=$(echo "$creds" | sed -n 's/^password=//p')
```

## Git

Bot Actions commituje `data/ output/ docs/` po każdym runie — przed pushem zawsze `git pull --rebase`. Wzorzec pracy: zmiana → testy jak wyżej → commit + push → użytkownik testuje przez FIRE/Light FIRE z dashboardu. Ręczny FIRE tego samego dnia **zastępuje** dzisiejsze wiersze w obu CSV (dedup po dacie w `append_history`).

## Architektura

Dwa pliki Pythona, reszta to dane:

**`tracker.py`** — cały pipeline w `main()`:
1. **Discovery** (`run_discovery`) — SerpAPI google + google_shopping per kraj z `settings.serpapi_countries` (+ opcjonalnie Serper.dev/Tavily/Brave); dopisuje URL-e do `data/sources.json`. Tryb `weekly`: przy `GITHUB_EVENT_NAME=schedule` tylko w poniedziałki; ręczny dispatch zawsze pełne discovery, chyba że `SKIP_DISCOVERY=1`. Shopping odpytywany tylko pierwszą frazą i bez cudzysłowów.
2. **Monitoring** (`fetch_offers`) — pobiera każdy URL, ekstrakcja ceny z JSON-LD schema.org → fallback meta OpenGraph → `__NEXT_DATA__`. Blokada botów (403/429/503 albo HTTP 200 z interstitialem rozpoznanym przez `_is_challenge`) → fallback headless Chromium (Playwright, leniwy start). Gdy strona bez ceny: auto-crawl 1 poziom (szuka linku do karty produktu po tokenach nazwy). Kolejność filtrów per URL: EAN (miękki, `ean_strict` twardy) → `require_tokens` (URL + `<title>` + ident oferty; `"a|b"` = alternatywa) → wariant (ident oferty, przy cenie zbiorczej także URL/tytuł z granicami słowa; `variant_strict` twardy) → dostępność → waluta/region → widełki `min_pln`/`max_pln`. Po pętli `drop_outliers`: przy ≥3 ofertach odpada cena < 25% mediany.
3. **Blind spoty** (`fill_blind_spots`) — domeny, które odrzuciły pobranie (i requests, i przeglądarkę; np. bike24 = Akamai, r2-bike = Cloudflare), dostają cenę z Google: najpierw feed Google Shopping — dostawcy w kolejności Serper.dev (`SERPER_API_KEY`; 2500 darmowych zapytań) → SerpAPI (chroniony `settings.serpapi_reserve`, domyślnie 10), wspólny budżet `settings.shopping_budget` zapytań/run (domyślnie 4) — potem indeks Googlebota przez Programmable Search (`GOOGLE_API_KEY`+`GOOGLE_CX`, `settings.cse_budget`/run, domyślnie 15; 100 zapytań/dzień darmowe, cena może być sprzed kilku dni; **uwaga: od 2026-01-20 PSE bez opcji „cała sieć"** — domeny blind spotów trzeba dopisywać do wyszukiwarki ręcznie, limit 50). Bing Search API nie istnieje (wyłączone 2025-08-11), Brave nie zwraca cen (tylko discovery, od 02.2026 bez darmowego planu). Filtry jakości na tytule oferty (`_title_ok`: tokeny produktu + `require_tokens` + wariant). Takie oferty mają `via=shopping|google` w `all_offers.csv` i znacznik „Google" w audycie dashboardu.
4. **FX** — NBP tabela A, fallback frankfurter.app; wszystko przeliczane na PLN.
5. **Zapis** — `data/history.csv` (najniższa cena/produkt/dzień), `data/all_offers.csv` (pełny audyt), Excel `output/prices.xlsx`, log `data/last_run.log` (osadzany w dashboardzie).

**`dashboard.py`** — jeden wielki raw-string `TEMPLATE` (HTML+CSS+JS SPA, Chart.js + js-yaml z CDN). `build_dashboard()` wstrzykuje JSON payload (historia + audyt z ostatnich 120 dni + log + quota SerpAPI) i zapisuje **dwie kopie**: `output/dashboard.html` i `docs/index.html` (GitHub Pages z `/docs`). SPA ma zakładki: Główna (karuzela) / Produkty (tabela → klik = szczegóły) / Diagnostyka (log z filtrami) / Konfiguracja. Konfiguracja edytuje `products.yaml` **przez GitHub API** (PUT contents; komentarze YAML giną przy zapisie). FIRE/Light FIRE = workflow dispatch z inputem `discovery: full|skip`.

**Kluczowy inwariant:** `id` produktu z `products.yaml` jest kluczem wszędzie — `product_id` w obu CSV, klucz w `sources.json`, arkusz Excela, zakładka dashboardu. Zmiana `id` urywa ciągłość historii; duplikat `id` scala bazy URL-i i miesza oferty (tracker pomija duplikat z błędem, dashboard blokuje zapis).

**Baza źródeł (`data/sources.json`) jest tylko dopisywana** — to główne aktywo projektu. Sklep niedostępny danego dnia zostaje w bazie. URL-e normalizowane (`normalize_url` usuwa `srsltid`, `utm_*` itd.). Agregatory cen (ceneo, idealo, geizhals…) i marketplace'y (eBay, Amazon) blokowane globalnie w `BLOCKED_DOMAINS` z dopasowaniem subdomen.

## Limit SerpAPI

Plan Free: 250 zapytań/mies. Pełny FIRE przy ~10 produktach ≈ 90 zapytań (frazy × kraje × silniki + Shopping). Timeout SerpAPI i tak zużywa zapytanie (stąd `SERPAPI_TIMEOUT=60`). Do testów zmian w monitoringu/dashboardzie używaj Light FIRE — nie zużywa limitu. Stan limitu: `data/serpapi_quota.json`; fallback Shopping dla blind spotów czyta ten plik i pomija się, gdy `left − serpapi_reserve ≤ 0` (wtedy ceny łata tylko warstwa CSE, która ma osobny darmowy limit dzienny Google).
