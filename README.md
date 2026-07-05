# Price Tracker — monitoring najniższych cen (Europa kontynentalna)

Codziennie o 12:00 skrypt:
1. **Discovery** — pyta wyszukiwarki (SerpAPI: zwykłe Google **oraz Google Shopping** per kraj z `serpapi_countries`; opcjonalnie Tavily/Brave) o EAN / frazy każdego produktu i dopisuje nowo znalezione sklepy do bazy (`data/sources.json`). URL-e są normalizowane (usuwane `srsltid`, `utm_*`, `gclid` itd.), więc baza nie puchnie od duplikatów. Google Shopping odpytywany jest tylko pierwszą (najprecyzyjniejszą) frazą — EAN-em, gdy jest podany — żeby oszczędzać limit. Baza URL-i rośnie w czasie — to Twoje główne aktywo.
2. **Monitoring** — odwiedza każdy znany URL, wyciąga cenę i dostępność z danych strukturalnych strony (JSON-LD `schema.org/Product`, fallback: meta OpenGraph oraz `__NEXT_DATA__` dla sklepów headless). Oferty niedostępne (`OutOfStock`) są odrzucane. Gdy URL nie ma ceny (np. strona kategorii lub artykuł), skrypt sam szuka na niej linku do karty tego produktu (dopasowanie po kodzie modelu / tokenach nazwy), sprawdza go od razu i — jeśli znajdzie cenę — dopisuje do bazy URL-i. Jeśli produkt ma `ean`, skrypt sprawdza jego obecność w HTML sklepu i oznacza ofertę w logu `[EAN OK]` / `[EAN niepotwierdzony]` (uwaga: EAN-y bywają nadawane per rozmiar/kolor, więc brak kodu to ostrzeżenie, nie błąd). Dla problematycznych produktów `ean_strict: true` odrzuca oferty bez potwierdzonego EAN-u.
3. **Filtr geograficzny** — tylko Europa kontynentalna: blokada TLD `.uk` (i innych spoza Europy) oraz walut GBP/USD. Akceptowane waluty: PLN, EUR, CZK, DKK, SEK, NOK, CHF, HUF, RON, BGN.
4. **Przeliczenie na PLN** — po kursie średnim NBP z danego dnia (tabela A), fallback: frankfurter.app (kursy EBC).
5. **Zapis** — najniższa cena per produkt trafia do `data/history.csv` (data, produkt, cena PLN, cena oryginalna, waluta, sklep, **URL źródła**). Pełny audyt wszystkich ofert: `data/all_offers.csv`.
6. **Raport Excel** — `output/prices.xlsx` regenerowany po każdym uruchomieniu: arkusz *Podsumowanie*, arkusz *Historia* i osobny arkusz z **wykresem dzień → najniższa cena** dla każdego produktu.

Lista produktów w `products.yaml` — możesz dodawać/usuwać wpisy w dowolnym momencie, skrypt zawsze przetwarza cały aktualny zakres, a kolejne daty dopisują się automatycznie.

---

## Konfiguracja krok po kroku

### 1. Repozytorium
1. Utwórz **prywatne** repo na GitHubie i wgraj zawartość tego folderu.
2. W repo: *Settings → Actions → General → Workflow permissions* → zaznacz **Read and write permissions** (bot musi commitować wyniki).

### 2. Silnik wyszukiwania (discovery)

> Uwaga: Google Programmable Search wycofał opcję „przeszukuj cały internet" dla nowych
> wyszukiwarek (całość znika 2027-01-01) — dlatego domyślnym silnikiem jest SerpAPI.

**SerpAPI (zalecane):** zarejestruj się na https://serpapi.com (plan Free, ~100 wyszukiwań/mies.,
prawdziwe wyniki Google — najlepszy zasięg dla zapytań EAN). Skopiuj API Key z dashboardu →
sekret `SERPAPI_KEY`.

**Tavily (zapas / większy limit):** https://tavily.com (plan Free, ~1000 zapytań/mies.) →
sekret `TAVILY_API_KEY`.

**Brave:** https://brave.com/search/api (obecnie bez planu darmowego — kredyty $5/mies.,
wymagana karta) → sekret `BRAVE_API_KEY`.

Skrypt używa wszystkich skonfigurowanych silników naraz i łączy wyniki. Dla oszczędzania
limitu SerpAPI, przy runach z harmonogramu discovery wykonuje się raz w tygodniu
(poniedziałki; `settings.discovery: "weekly"` w `products.yaml`, możesz zmienić na `"daily"`).
Ręczny FIRE **zawsze** robi pełne discovery. Monitoring znanych URL-i działa codziennie
niezależnie od discovery i nie zużywa żadnego limitu.

### 3. Sekrety w repo
*Settings → Secrets and variables → Actions → New repository secret*:
- `SERPAPI_KEY` (zalecany minimalny zestaw)
- opcjonalnie: `TAVILY_API_KEY`, `BRAVE_API_KEY`, `GOOGLE_API_KEY`+`GOOGLE_CX` (legacy)

Bez sekretów skrypt też działa — pominie discovery i sprawdzi tylko URL-e już zapisane w `data/sources.json` + `seed_urls` z konfiguracji.

### 4. Produkty
Edytuj `products.yaml`. Minimalny wpis:

```yaml
  - id: FM2797
    name: "Salsa Cutthroat C Frameset"
    ean: "0754625xxxxxx"      # mocno zalecane - najprecyzyjniejsze wyszukiwanie
    queries:
      - '"FM2797"'
```

Wskazówki:
- `ean` daje najczystsze wyniki (sklepy publikują EAN dla Google Shopping). Znajdziesz go na stronie dowolnego sklepu z produktem albo w danych producenta.
- `seed_urls` — jeśli znasz już konkretne sklepy, wklej linki do stron produktowych; będą sprawdzane od pierwszego dnia.
- `exclude_domains` — czarna lista domen dla danego produktu (np. sklep pokazujący inną wersję).
- `min_pln` / `max_pln` — widełki cenowe (w PLN); oferty poza nimi są odrzucane. Najskuteczniejszy filtr na „szum": części zamienne, akcesoria i błędne dopasowania (np. 30 zł za grupę napędową).
- `require_tokens` — lista słów, które muszą wystąpić w URL-u, tytule strony lub nazwie oferty (np. `carbon`, `s14`); wpis `"a|b"` oznacza „a LUB b" (przydatne na wersje językowe: `chain|kette|catena|łańcuch`).
- **Każdy produkt musi mieć unikalne `id`** — duplikat scala bazy URL-i i miesza oferty różnych produktów (skrypt pomija zduplikowane wpisy z błędem w logu, dashboard blokuje zapis).
- Dodatkowe zabezpieczenie automatyczne: przy ≥3 ofertach produktu cena poniżej 25% mediany jest odrzucana jako outlier (prawdziwe promocje −40/−60% przechodzą bez problemu).
- Agregatory cen (ceneo, idealo, geizhals, arukereso…) i marketplace'y (eBay, Amazon, AliExpress) są blokowane globalnie — pokazują ceny historyczne/aukcyjne, nie sklepowe.

### 5. Uruchomienie
- Automatycznie: codziennie o **12:00 CEST** (cron `0 10 * * *` w UTC). Zimą, przy zmianie czasu na CET, podmień cron na `0 11 * * *` w `.github/workflows/price-tracker.yml`, żeby zostać przy 12:00. Uwaga: GitHub potrafi opóźnić crony o kilka–kilkanaście minut przy dużym obciążeniu.
- Ręcznie: zakładka *Actions → Price Tracker → Run workflow* (przydatne do pierwszego testu).

### Uruchomienie lokalne (opcjonalnie)
```bash
pip install -r requirements.txt
set GOOGLE_API_KEY=...   # Windows;  na Linux/Mac: export
set GOOGLE_CX=...
python tracker.py
```

---

## Struktura danych

| Plik | Rola |
|---|---|
| `products.yaml` | konfiguracja produktów (edytujesz Ty) |
| `data/sources.json` | baza znanych URL-i sklepów per produkt (rośnie automatycznie) |
| `data/history.csv` | historia: najniższa cena / produkt / dzień + URL źródła |
| `data/all_offers.csv` | audyt: wszystkie znalezione oferty każdego dnia |
| `output/prices.xlsx` | raport z podsumowaniem, historią i wykresami |
| `output/dashboard.html` | panel (SPA) — kopia trafia też do `docs/index.html` (GitHub Pages) |
| `data/last_run.log` | log ostatniego przebiegu (zakładka Diagnostyka w panelu) |

---

## Centrum dowodzenia (`output/dashboard.html`)

Interaktywny panel (SPA) regenerowany przy każdym uruchomieniu — otwierasz w przeglądarce, lokalnie lub prosto z repo.

**Główna:** karuzela wykresów (jeden produkt na raz, strzałki ‹ › / klawiatura / kropki), zakres: Tydzień / Miesiąc / Kwartał / Max, tooltip każdego punktu pokazuje cenę **i sklep**, pod spodem sygnał KUP (gdy cena ≤ ceny docelowej) oraz tabela wszystkich dzisiejszych ofert z linkami.

**Zakładka Produkty:** tabela przeglądowa wszystkich produktów (aktualna cena, minimum historyczne, cel z sygnałem KUP, sklep) — kliknięcie wiersza otwiera widok szczegółowy produktu. Nawigacja ma stałe 4 zakładki niezależnie od liczby produktów.

**Widok szczegółowy produktu:** statystyki (aktualna najniższa, minimum historyczne, średnia okresu z odchyleniem %, liczba sklepów), wykres cen **per sklep** (osobna linia dla każdego sklepu z audytu ofert), tabela ostatnich ofert i pełna historia dziennych minimów z linkami.

**Diagnostyka:** log ostatniego przebiegu wprost w panelu — kafelki z licznikami (oferty z ceną, błędy HTTP, brak danych o cenie, odfiltrowane, auto-crawl) działają jak filtry, linie logu są kolorowane wg kategorii. „Odśwież dane" pobiera świeży log z repo.

**Konfiguracja:** edycja listy produktów (ID/kod, nazwa, EAN, cena docelowa, wariant, worldwide, widełki min/max PLN, wymagane słowa, frazy, seed URLs, wykluczenia) bezpośrednio z panelu. Zapis blokuje zduplikowane ID. Zapis nadpisuje `products.yaml` w repo przez GitHub API — czyli dokładnie ten plik, którego używa workflow. Przycisk „Zapisz + Fire" od razu zbiera ceny dla nowej listy. Uwaga: zapis z panelu usuwa komentarze z pliku YAML.

**Nagłówek:** dioda statusu, data **ostatniego skutecznego odświeżenia** (ostatni udany run workflow z GitHub API; bez tokenu — data ostatniego pomiaru w danych), „Odśwież dane" (pobiera aktualne CSV z repo bez ściągania pliku), **▶ FIRE** (ręczne uruchomienie workflow; po zakończeniu panel sam pobiera świeże dane).

Wymagania FIRE / odświeżania / konfiguracji:
1. W `products.yaml` uzupełnij `settings.github_repo` (np. `"twojlogin/price-tracker"`).
2. Token: GitHub → *Settings → Developer settings → Fine-grained tokens* → dostęp tylko do tego repo, uprawnienia **Contents: Read and write** oraz **Actions: Read and write**. Panel poprosi o token przy pierwszym użyciu i trzyma go wyłącznie w Twojej przeglądarce (localStorage).

Uwaga techniczna: w pliku HTML osadzony jest pełny `history.csv` oraz audyt ofert z ostatnich 120 dni (żeby plik nie puchł latami); „Odśwież dane" zawsze pobiera komplet z repo.

Alternatywa ręcznego uruchomienia: zakładka *Actions → Price Tracker → Run workflow* w GitHubie.

### Dashboard pod stałym adresem (GitHub Pages)

Skrypt zapisuje kopię panelu także do `docs/index.html`. Żeby mieć dashboard zawsze pod ręką (bez pobierania pliku):
1. Repo → *Settings → Pages* → Source: **Deploy from a branch** → Branch: `main`, folder `/docs` → Save.
2. Po chwili panel będzie dostępny pod `https://<login>.github.io/<repo>/` i będzie się aktualizował po każdym runie workflow.

Uwaga: przy **prywatnym** repo strona Pages jest publiczna na planie Free (prywatne Pages wymagają planu Pro/Enterprise) — panel nie zawiera tokenu (token żyje tylko w Twojej przeglądarce), ale osadza historię cen i nazwy produktów. Jeśli to problem, po prostu nie włączaj Pages i otwieraj `output/dashboard.html` lokalnie.

## Wyjątki od filtra Europy (`worldwide`)

Produkt z `worldwide: true` (np. Lauf Carbonara) omija blokadę TLD i dopuszcza dodatkowo waluty USD/GBP/CAD/AUD — ceny nadal przeliczane są na PLN po kursie NBP z danego dnia. Pozostałe produkty trzymają się Europy kontynentalnej.

## Znane ograniczenia
- Sklep bez danych strukturalnych (JSON-LD / meta) zostanie zalogowany jako „brak danych o cenie" — takie przypadki widać w logach Actions i można je obsłużyć punktowo.
- Nieliczne sklepy blokują boty (Cloudflare) — pojawią się jako błąd HTTP w logach; zwykle wystarczy pominąć, bo cena jest też gdzie indziej.
- Discovery znajduje tylko sklepy zaindeksowane przez Google z EAN-em/numerem katalogowym na stronie — czyli ~wszystkie realne, ale nie daje matematycznej gwarancji 100%.
