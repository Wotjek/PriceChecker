#!/usr/bin/env python3
"""
Price Tracker - monitoring najnizszych cen w sklepach Europy kontynentalnej.

Pipeline:
  1. DISCOVERY  - Google Programmable Search (EAN / frazy) -> nowe URL-e sklepow
  2. MONITORING - pobranie stron, ekstrakcja ceny+dostepnosci z JSON-LD / meta
  3. FX         - przeliczenie na PLN po kursie NBP z danego dnia (fallback: frankfurter.app)
  4. HISTORIA   - dopisanie wiersza (data, produkt, najnizsza cena, sklep, URL) do CSV
  5. RAPORT     - regeneracja pliku Excel z historia i wykresem dla kazdego produktu
"""

import csv
import json
import os
import re
import sys
import time
from datetime import date
from pathlib import Path
from urllib.parse import urlparse

import requests
import yaml
from bs4 import BeautifulSoup

ROOT = Path(__file__).parent
DATA = ROOT / "data"
OUTPUT = ROOT / "output"
PRODUCTS_FILE = ROOT / "products.yaml"
SOURCES_FILE = DATA / "sources.json"      # baza znanych URL-i per produkt
HISTORY_FILE = DATA / "history.csv"       # najlepsza cena / produkt / dzien
OFFERS_FILE = DATA / "all_offers.csv"     # wszystkie znalezione oferty (audyt)
QUOTA_FILE = DATA / "serpapi_quota.json"  # stan limitu darmowych zapytan SerpAPI
EXCEL_FILE = OUTPUT / "prices.xlsx"

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")
TIMEOUT = 25
SLEEP_BETWEEN_FETCHES = 2.0

# --- Europa kontynentalna: dozwolone waluty i TLD ---------------------------
ALLOWED_CURRENCIES = {"PLN", "EUR", "CZK", "DKK", "SEK", "NOK", "CHF",
                      "HUF", "RON", "BGN"}
EU_TLDS = {"pl", "de", "nl", "fr", "it", "es", "be", "at", "cz", "sk", "dk",
           "se", "fi", "no", "pt", "hu", "ro", "si", "hr", "lt", "lv", "ee",
           "gr", "bg", "lu", "ch", "li", "ie", "eu"}
NEUTRAL_TLDS = {"com", "net", "org", "shop", "bike", "cc", "io", "store"}
BLOCKED_TLDS = {"uk", "gg", "je", "im", "us", "ca", "au", "nz", "jp", "cn",
                "in", "br", "mx", "za", "kr", "sg", "hk", "tr", "ru", "by"}
BLOCKED_DOMAINS = {"ebay.com", "ebay.de", "ebay.pl", "amazon.com",
                   "idealo.de", "idealo.pl", "google.com", "youtube.com",
                   "facebook.com", "reddit.com", "pinterest.com",
                   "salsacycles.com",  # strona producenta bez cen sklepowych
                   # portale nieruchomosci (kolizje nazw typu "FM2797" = droga w Teksasie)
                   "homes.com", "redfin.com", "har.com", "compass.com",
                   "zillow.com", "realtor.com", "trulia.com",
                   # media/recenzje - artykuly, nie sklepy
                   "fat-bike.com", "singletracks.com", "bikeradar.com",
                   "pinkbike.com", "bikerumor.com", "cyclingnews.com"}
BLOCKED_PATH_RE = re.compile(r"/(blogs?|news|review|artykul|magazin)e?s?/", re.I)

IN_STOCK = {"instock", "limitedavailability", "onlineonly"}


# ============================================================ helpers =======

LOG_BUFFER = []


def log(msg):
    print(msg, flush=True)
    LOG_BUFFER.append(str(msg))


def save_run_log():
    DATA.mkdir(exist_ok=True)
    (DATA / "last_run.log").write_text("\n".join(LOG_BUFFER) + "\n",
                                       encoding="utf-8")


def domain_of(url):
    d = urlparse(url).netloc.lower()
    return d[4:] if d.startswith("www.") else d


def tld_of(domain):
    return domain.rsplit(".", 1)[-1]


WORLDWIDE_CURRENCIES = ALLOWED_CURRENCIES | {"USD", "GBP", "CAD", "AUD"}


def url_allowed(url, extra_excluded, worldwide=False):
    if BLOCKED_PATH_RE.search(urlparse(url).path or ""):
        return False
    return domain_allowed(domain_of(url), extra_excluded, worldwide)


def domain_allowed(domain, extra_excluded, worldwide=False):
    if not domain or domain in BLOCKED_DOMAINS or domain in extra_excluded:
        return False
    if worldwide:
        return True  # produkt globalny (np. dostepny glownie w US)
    if any(domain.endswith("." + b) or tld_of(domain) == b for b in BLOCKED_TLDS):
        return False
    tld = tld_of(domain)
    return tld in EU_TLDS or tld in NEUTRAL_TLDS


# ======================================================== FX (kurs dnia) ====

def get_fx_rates():
    """Zwraca slownik {waluta: kurs_PLN} z NBP (tabela A), fallback frankfurter.app."""
    rates = {"PLN": 1.0}
    try:
        r = requests.get("https://api.nbp.pl/api/exchangerates/tables/A?format=json",
                         timeout=TIMEOUT)
        r.raise_for_status()
        for row in r.json()[0]["rates"]:
            rates[row["code"]] = float(row["mid"])
        log(f"[FX] Kursy NBP pobrane ({len(rates)} walut)")
        return rates
    except Exception as e:
        log(f"[FX] NBP niedostepne ({e}), probuje frankfurter.app")
    try:
        r = requests.get("https://api.frankfurter.app/latest?from=PLN", timeout=TIMEOUT)
        r.raise_for_status()
        for code, v in r.json()["rates"].items():
            rates[code] = 1.0 / float(v)  # kurs waluty w PLN
        log(f"[FX] Kursy frankfurter pobrane ({len(rates)} walut)")
    except Exception as e:
        log(f"[FX] BLAD: brak kursow walut ({e}) - tylko oferty w PLN beda uzyte")
    return rates


# ========================================================== discovery =======

def google_search(query, api_key, cx, pages=1):
    """Legacy: Google Programmable Search (dziala tylko dla starych wyszukiwarek
    z wlaczonym 'Search the entire web'; funkcja wygasa 2027-01-01)."""
    urls = []
    for page in range(pages):
        params = {"key": api_key, "cx": cx, "q": query,
                  "num": 10, "start": 1 + page * 10}
        try:
            r = requests.get("https://www.googleapis.com/customsearch/v1",
                             params=params, timeout=TIMEOUT)
            if r.status_code == 429:
                log("[DISCOVERY][google] Limit dzienny wyczerpany")
                return urls
            r.raise_for_status()
            items = r.json().get("items", [])
            urls += [it["link"] for it in items if "link" in it]
            if len(items) < 10:
                break
        except Exception as e:
            log(f"[DISCOVERY][google] Blad zapytania '{query}': {e}")
            break
        time.sleep(0.5)
    return urls


def serpapi_search(query, api_key, gl=None):
    """SerpAPI - prawdziwe wyniki Google (plan darmowy: 250 zapytan/mies.).
    gl = kod kraju (np. 'de', 'pl') - wyniki z lokalnej wersji Google."""
    try:
        params = {"engine": "google", "q": query, "num": 20, "api_key": api_key}
        if gl:
            params.update({"gl": gl, "google_domain": f"google.{gl}"})
        r = requests.get("https://serpapi.com/search.json",
                         params=params, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        if j.get("error"):
            log(f"[DISCOVERY][serpapi] {j['error']}")
            return []
        return [it["link"] for it in j.get("organic_results", []) if it.get("link")]
    except Exception as e:
        log(f"[DISCOVERY][serpapi] Blad zapytania '{query}': {e}")
        return []


def tavily_search(query, api_key):
    """Tavily - web search API (plan darmowy: ~1000 zapytan/mies.)."""
    try:
        r = requests.post("https://api.tavily.com/search",
                          json={"api_key": api_key, "query": query,
                                "max_results": 20}, timeout=TIMEOUT)
        r.raise_for_status()
        return [it["url"] for it in r.json().get("results", []) if it.get("url")]
    except Exception as e:
        log(f"[DISCOVERY][tavily] Blad zapytania '{query}': {e}")
        return []


def brave_search(query, api_key):
    """Brave Search API (plan platny/kredytowy)."""
    try:
        r = requests.get("https://api.search.brave.com/res/v1/web/search",
                         params={"q": query, "count": 20},
                         headers={"X-Subscription-Token": api_key,
                                  "Accept": "application/json"}, timeout=TIMEOUT)
        r.raise_for_status()
        return [it["url"] for it in r.json().get("web", {}).get("results", [])
                if it.get("url")]
    except Exception as e:
        log(f"[DISCOVERY][brave] Blad zapytania '{query}': {e}")
        return []


def _discovery_engines():
    """Buduje liste dostepnych silnikow na podstawie sekretow w env."""
    engines = []
    if os.environ.get("SERPAPI_KEY", "").strip():
        k = os.environ["SERPAPI_KEY"].strip()
        engines.append(("serpapi", lambda q, gl=None: serpapi_search(q, k, gl)))
    if os.environ.get("TAVILY_API_KEY", "").strip():
        k = os.environ["TAVILY_API_KEY"].strip()
        engines.append(("tavily", lambda q: tavily_search(q, k)))
    if os.environ.get("BRAVE_API_KEY", "").strip():
        k = os.environ["BRAVE_API_KEY"].strip()
        engines.append(("brave", lambda q: brave_search(q, k)))
    gk, cx = os.environ.get("GOOGLE_API_KEY", "").strip(), os.environ.get("GOOGLE_CX", "").strip()
    if gk and cx:
        engines.append(("google", lambda q: google_search(q, gk, cx)))
    return engines


def run_discovery(products, sources, settings):
    engines = _discovery_engines()
    if not engines:
        log("[DISCOVERY] Brak kluczy (SERPAPI_KEY / TAVILY_API_KEY / BRAVE_API_KEY / "
            "GOOGLE_API_KEY+CX) - pomijam discovery, uzywam znanych URL-i")
        return sources

    # oszczedzanie limitu: przy trybie weekly harmonogram robi discovery tylko
    # w poniedzialki; reczny FIRE (workflow_dispatch) i run lokalny - zawsze
    mode = str(settings.get("discovery") or "weekly").lower()
    event = os.environ.get("GITHUB_EVENT_NAME", "")
    if event == "schedule" and mode == "weekly" and date.today().weekday() != 0:
        log(f"[DISCOVERY] Tryb weekly - dzis pomijam (silniki: "
            f"{[n for n, _ in engines]}), monitoring dziala normalnie")
        return sources

    log(f"[DISCOVERY] Silniki: {[n for n, _ in engines]}")
    today = date.today().isoformat()
    for p in products:
        pid = p["id"]
        known = sources.setdefault(pid, {})
        excluded = set(p.get("exclude_domains") or [])
        worldwide = bool(p.get("worldwide"))
        queries = []
        if p.get("ean"):
            queries.append(f'"{p["ean"]}"')
        queries += p.get("queries") or []
        if not queries:
            queries = [f'"{p["name"]}"']

        # produkty EU: pytaj lokalne wersje Google (serpapi); worldwide: domyslna (US)
        eu_countries = settings.get("serpapi_countries") or ["de", "pl"]
        found = 0
        for q in queries:
            for name, fn in engines:
                countries = ([None] if (worldwide or name != "serpapi")
                             else list(eu_countries))
                for gl in countries:
                    urls = fn(q, gl=gl) if name == "serpapi" else fn(q)
                    for url in urls:
                        dom = domain_of(url)
                        if url not in known and url_allowed(url, excluded, worldwide):
                            known[url] = {"domain": dom, "first_seen": today,
                                          "via": name + (f":{gl}" if gl else "")}
                            found += 1
                    time.sleep(0.4)
        log(f"[DISCOVERY] {pid}: +{found} nowych URL-i (razem {len(known)})")
    return sources


def save_serpapi_quota():
    """Zapisuje stan limitu SerpAPI (endpoint /account nie zuzywa zapytan)."""
    key = os.environ.get("SERPAPI_KEY", "").strip()
    if not key:
        return
    try:
        r = requests.get("https://serpapi.com/account",
                         params={"api_key": key}, timeout=TIMEOUT)
        r.raise_for_status()
        j = r.json()
        data = {"plan": j.get("plan_name", ""),
                "per_month": j.get("searches_per_month"),
                "used": j.get("this_month_usage"),
                "left": j.get("plan_searches_left"),
                "checked": date.today().isoformat()}
        DATA.mkdir(exist_ok=True)
        QUOTA_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
        log(f"[SERPAPI] Limit: pozostalo {data['left']} z {data['per_month']} "
            f"(zuzyte w tym miesiacu: {data['used']})")
    except Exception as e:
        log(f"[SERPAPI] Nie udalo sie pobrac stanu limitu: {e}")


# ========================================================== extraction ======

PRODUCT_TYPES = {"product", "productgroup", "offer", "aggregateoffer"}


def _iter_jsonld_nodes(soup):
    """Iteruje po wezlach JSON-LD typu Product/ProductGroup/Offer, zbiera tez
    liste wszystkich napotkanych typow (diagnostyka)."""
    seen_types = set()
    nodes = []
    for tag in soup.find_all("script", type="application/ld+json"):
        try:
            data = json.loads(tag.string or "")
        except Exception:
            continue
        stack = data if isinstance(data, list) else [data]
        while stack:
            node = stack.pop()
            if not isinstance(node, dict):
                continue
            if "@graph" in node:
                stack += [n for n in node["@graph"] if isinstance(n, dict)]
            t = node.get("@type", "")
            types = t if isinstance(t, list) else [t]
            tl = {str(x).lower() for x in types if x}
            seen_types |= tl
            if tl & PRODUCT_TYPES:
                nodes.append(node)
    return nodes, seen_types


def _norm_availability(val):
    if not val:
        return ""
    return str(val).rsplit("/", 1)[-1].strip().lower()


def _parse_price(val):
    if val is None:
        return None
    s = str(val).strip().replace("\xa0", "").replace(" ", "")
    s = re.sub(r"[^\d,.\-]", "", s)
    if "," in s and "." in s:
        s = s.replace(",", "") if s.rfind(".") > s.rfind(",") else s.replace(".", "").replace(",", ".")
    elif "," in s:
        s = s.replace(",", ".")
    try:
        v = float(s)
        return v if v > 0 else None
    except ValueError:
        return None


def _ident_of(obj):
    parts = []
    for k in ("sku", "name", "mpn", "url", "@id"):
        v = obj.get(k)
        if isinstance(v, dict):
            v = v.get("name", "")
        if v:
            parts.append(str(v))
    return " ".join(parts).lower()


def _collect_offers(obj, ident, out):
    """Zbiera oferty z pola offers danego obiektu (obsluga AggregateOffer,
    zagniezdzonych offers[] i priceSpecification)."""
    offs = obj.get("offers")
    if not offs:
        return
    offs = list(offs) if isinstance(offs, list) else [offs]
    for off in offs:
        if not isinstance(off, dict):
            continue
        inner = off.get("offers")
        if isinstance(inner, list):
            offs += [o for o in inner if isinstance(o, dict)]
        price = _parse_price(off.get("price", off.get("lowPrice")))
        currency = str(off.get("priceCurrency", "")).upper().strip()
        if price is None or not currency:
            ps = off.get("priceSpecification")
            if isinstance(ps, list):
                ps = ps[0] if ps else None
            if isinstance(ps, dict):
                price = price if price is not None else _parse_price(ps.get("price"))
                currency = currency or str(ps.get("priceCurrency", "")).upper().strip()
        avail = _norm_availability(off.get("availability"))
        io = off.get("itemOffered")
        io_ident = _ident_of(io) if isinstance(io, dict) else ""
        if price and currency:
            out.append({"price": price, "currency": currency, "avail": avail,
                        "ident": (_ident_of(off) + " " + io_ident + " " + ident).strip()})


def extract_offers(html):
    """Zwraca (lista_kandydatow, typy_jsonld). Kandydat: dict(price, currency,
    avail, ident) - ident sluzy dopasowaniu wariantu (np. rozmiaru)."""
    soup = BeautifulSoup(html, "html.parser")
    nodes, seen_types = _iter_jsonld_nodes(soup)
    out = []
    for node in nodes:
        ident = _ident_of(node)
        t = node.get("@type", "")
        types = {str(x).lower() for x in (t if isinstance(t, list) else [t])}
        if types & {"offer", "aggregateoffer"}:  # samodzielny wezel Offer
            price = _parse_price(node.get("price", node.get("lowPrice")))
            currency = str(node.get("priceCurrency", "")).upper().strip()
            avail = _norm_availability(node.get("availability"))
            if price and currency:
                out.append({"price": price, "currency": currency,
                            "avail": avail, "ident": ident})
        _collect_offers(node, ident, out)
        for v in (node.get("hasVariant") or []):        # ProductGroup
            if isinstance(v, dict):
                _collect_offers(v, _ident_of(v), out)

    if not out:  # fallback: meta OpenGraph / microdata
        mp = (soup.find("meta", attrs={"property": "product:price:amount"})
              or soup.find("meta", attrs={"property": "og:price:amount"})
              or soup.find("meta", attrs={"itemprop": "price"}))
        mc = (soup.find("meta", attrs={"property": "product:price:currency"})
              or soup.find("meta", attrs={"property": "og:price:currency"})
              or soup.find("meta", attrs={"itemprop": "priceCurrency"}))
        ma = (soup.find("meta", attrs={"property": "product:availability"})
              or soup.find("link", attrs={"itemprop": "availability"})
              or soup.find("meta", attrs={"itemprop": "availability"}))
        if mp and mc:
            price = _parse_price(mp.get("content"))
            currency = str(mc.get("content", "")).upper().strip()
            avail = _norm_availability(ma.get("content") or ma.get("href")) if ma else ""
            if price and currency:
                out.append({"price": price, "currency": currency,
                            "avail": avail, "ident": ""})
    return out, seen_types


# ========================================================== monitoring ======

def fetch_offers(products, sources, rates):
    """Zwraca liste ofert: dict(product_id, name, url, domain, price, currency,
    price_pln, availability)."""
    session = requests.Session()
    session.headers.update({"User-Agent": UA, "Accept-Language": "en,de;q=0.9,pl;q=0.8"})
    offers = []

    for p in products:
        pid = p["id"]
        excluded = set(p.get("exclude_domains") or [])
        worldwide = bool(p.get("worldwide"))
        variant = str(p.get("variant") or "").strip().lower()
        strict = bool(p.get("variant_strict"))
        allowed_cur = WORLDWIDE_CURRENCIES if worldwide else ALLOWED_CURRENCIES
        urls = dict(sources.get(pid, {}))
        for u in p.get("seed_urls") or []:
            urls.setdefault(u, {"domain": domain_of(u), "first_seen": "seed"})

        log(f"[MONITOR] {pid}: sprawdzam {len(urls)} URL-i"
            + (f" (wariant: {variant})" if variant else ""))
        for url, meta in urls.items():
            dom = meta.get("domain") or domain_of(url)
            if not url_allowed(url, excluded, worldwide):
                continue
            try:
                r = session.get(url, timeout=TIMEOUT, allow_redirects=True)
                if r.status_code != 200:
                    log(f"  - {dom}: HTTP {r.status_code}")
                    continue
                final_url = r.url or url  # kanoniczny adres po przekierowaniach
                cands, seen_types = extract_offers(r.text)
            except Exception as e:
                log(f"  - {dom}: blad pobierania ({type(e).__name__})")
                continue
            finally:
                time.sleep(SLEEP_BETWEEN_FETCHES)

            if not cands:
                types = ", ".join(sorted(seen_types)) or "brak JSON-LD"
                log(f"  - {dom}: brak danych o cenie (typy na stronie: {types})")
                continue

            vnote = ""
            if variant:
                matching = [c for c in cands if variant in c["ident"]]
                if matching:
                    cands = matching
                    vnote = f" [wariant {variant} dopasowany]"
                elif any(c["ident"] for c in cands):
                    log(f"  - {dom}: brak wariantu '{variant}' wsrod ofert - pomijam")
                    continue
                elif strict:
                    log(f"  - {dom}: cena zbiorcza bez informacji o wariantach "
                        f"- pomijam (variant_strict)")
                    continue
                else:
                    vnote = f" [wariant {variant} NIEZWERYFIKOWANY - cena zbiorcza]"

            in_stock = [c for c in cands if not c["avail"] or c["avail"] in IN_STOCK]
            if not in_stock:
                log(f"  - {dom}: niedostepny ({cands[0]['avail']})")
                continue
            valid_cur = [c for c in in_stock if c["currency"] in allowed_cur]
            if not valid_cur:
                log(f"  - {dom}: waluta {in_stock[0]['currency']} poza dozwolonym "
                    f"regionem - pomijam")
                continue
            usable = [c for c in valid_cur if c["currency"] in rates]
            if not usable:
                log(f"  - {dom}: brak kursu {valid_cur[0]['currency']}")
                continue
            best = min(usable, key=lambda c: c["price"] * rates[c["currency"]])
            price, currency = best["price"], best["currency"]
            price_pln = round(price * rates[currency], 2)
            offers.append({"product_id": pid, "name": p["name"], "url": final_url,
                           "domain": dom, "price": price, "currency": currency,
                           "price_pln": price_pln,
                           "availability": best["avail"] or "instock"})
            log(f"  + {dom}: {price} {currency} = {price_pln} PLN{vnote}")
    return offers


# ============================================================ storage =======

HIST_COLS = ["date", "product_id", "product_name", "price_pln",
             "price_orig", "currency", "shop", "url", "offers_checked"]
OFFER_COLS = ["date", "product_id", "domain", "price", "currency",
              "price_pln", "availability", "url"]


def append_history(offers, products, today):
    DATA.mkdir(exist_ok=True)
    # pelny audyt ofert
    new_file = not OFFERS_FILE.exists()
    with OFFERS_FILE.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OFFER_COLS)
        if new_file:
            w.writeheader()
        for o in offers:
            w.writerow({"date": today, "product_id": o["product_id"],
                        "domain": o["domain"], "price": o["price"],
                        "currency": o["currency"], "price_pln": o["price_pln"],
                        "availability": o["availability"], "url": o["url"]})

    # historia: najlepsza cena per produkt; nadpisz jesli dzis juz byl wpis
    rows = []
    if HISTORY_FILE.exists():
        with HISTORY_FILE.open(newline="", encoding="utf-8") as f:
            rows = [r for r in csv.DictReader(f)]
    rows = [r for r in rows if not (r["date"] == today)]

    by_product = {}
    for o in offers:
        cur = by_product.get(o["product_id"])
        if cur is None or o["price_pln"] < cur["price_pln"]:
            by_product[o["product_id"]] = o
    counts = {}
    for o in offers:
        counts[o["product_id"]] = counts.get(o["product_id"], 0) + 1

    for p in products:
        pid = p["id"]
        best = by_product.get(pid)
        if best:
            rows.append({"date": today, "product_id": pid,
                         "product_name": p["name"],
                         "price_pln": best["price_pln"],
                         "price_orig": best["price"],
                         "currency": best["currency"],
                         "shop": best["domain"], "url": best["url"],
                         "offers_checked": counts.get(pid, 0)})
            log(f"[HISTORIA] {pid}: najnizsza {best['price_pln']} PLN "
                f"({best['domain']})")
        else:
            log(f"[HISTORIA] {pid}: brak dostepnych ofert dzisiaj")

    rows.sort(key=lambda r: (r["product_id"], r["date"]))
    with HISTORY_FILE.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=HIST_COLS)
        w.writeheader()
        w.writerows(rows)
    return rows


# ========================================================= excel report =====

def safe_sheet_name(name):
    return re.sub(r"[\[\]:*?/\\]", "-", str(name))[:31]


def build_excel(rows, products):
    from openpyxl import Workbook
    from openpyxl.chart import LineChart, Reference
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    OUTPUT.mkdir(exist_ok=True)
    wb = Workbook()

    hdr_font = Font(name="Arial", bold=True, color="FFFFFF")
    hdr_fill = PatternFill("solid", start_color="1F4E79")
    body_font = Font(name="Arial")
    money_fmt = "#,##0.00\\ \\z\\ł"

    def style_header(ws, ncols):
        for c in range(1, ncols + 1):
            cell = ws.cell(row=1, column=c)
            cell.font = hdr_font
            cell.fill = hdr_fill
            cell.alignment = Alignment(horizontal="center")
        ws.freeze_panes = "A2"

    # --- Podsumowanie ---
    ws = wb.active
    ws.title = "Podsumowanie"
    ws.append(["Produkt", "Nazwa", "Ostatni pomiar", "Aktualna najniższa (PLN)",
               "Minimum historyczne (PLN)", "Data minimum", "Sklep (aktualny)", "Link"])
    style_header(ws, 8)

    per_product = {}
    for r in rows:
        per_product.setdefault(r["product_id"], []).append(r)

    for p in products:
        pid = p["id"]
        hist = per_product.get(pid, [])
        if not hist:
            ws.append([pid, p["name"], "-", "-", "-", "-", "-", "-"])
            continue
        last = hist[-1]
        m = min(hist, key=lambda r: float(r["price_pln"]))
        row = [pid, p["name"], last["date"], float(last["price_pln"]),
               float(m["price_pln"]), m["date"], last["shop"], last["url"]]
        ws.append(row)
        rr = ws.max_row
        ws.cell(rr, 4).number_format = money_fmt
        ws.cell(rr, 5).number_format = money_fmt
        link = ws.cell(rr, 8)
        link.hyperlink = last["url"]
        link.font = Font(name="Arial", color="0563C1", underline="single")

    widths = [14, 34, 14, 22, 24, 14, 26, 50]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            if cell.font == Font():
                cell.font = body_font

    # --- Historia (pelna tabela) ---
    ws = wb.create_sheet("Historia")
    ws.append(["Data", "Produkt", "Nazwa", "Cena (PLN)", "Cena oryg.",
               "Waluta", "Sklep", "Link", "Ofert sprawdzonych"])
    style_header(ws, 9)
    for r in rows:
        ws.append([r["date"], r["product_id"], r["product_name"],
                   float(r["price_pln"]), float(r["price_orig"]), r["currency"],
                   r["shop"], r["url"], int(r.get("offers_checked") or 0)])
        ws.cell(ws.max_row, 4).number_format = money_fmt
    for i, w in enumerate([12, 14, 32, 14, 12, 8, 24, 48, 10], 1):
        ws.column_dimensions[get_column_letter(i)].width = w

    # --- Arkusz per produkt z wykresem ---
    for p in products:
        pid = p["id"]
        hist = per_product.get(pid, [])
        ws = wb.create_sheet(safe_sheet_name(pid))
        ws.append(["Data", "Najniższa cena (PLN)", "Sklep", "Link"])
        style_header(ws, 4)
        for r in hist:
            ws.append([r["date"], float(r["price_pln"]), r["shop"], r["url"]])
            ws.cell(ws.max_row, 2).number_format = money_fmt
        for i, w in enumerate([12, 20, 26, 50], 1):
            ws.column_dimensions[get_column_letter(i)].width = w

        n = len(hist)
        if n >= 1:
            chart = LineChart()
            chart.title = f"{p['name']} - najniższa cena dzienna (PLN)"
            chart.style = 12
            chart.y_axis.title = "PLN"
            chart.x_axis.title = "Data"
            chart.height = 9
            chart.width = 22
            data = Reference(ws, min_col=2, min_row=1, max_row=1 + n)
            cats = Reference(ws, min_col=1, min_row=2, max_row=1 + n)
            chart.add_data(data, titles_from_data=True)
            chart.set_categories(cats)
            s = chart.series[0]
            s.marker.symbol = "circle"
            s.marker.size = 6
            s.smooth = False
            ws.add_chart(chart, "F2")

    wb.save(EXCEL_FILE)
    log(f"[EXCEL] Zapisano {EXCEL_FILE}")


# =============================================================== main =======

def main():
    with PRODUCTS_FILE.open(encoding="utf-8") as f:
        cfg = yaml.safe_load(f) or {}
    products = cfg.get("products") or []
    settings = cfg.get("settings") or {}
    if not products:
        log("Brak produktow w products.yaml - koniec.")
        return 0
    log(f"Produkty: {[p['id'] for p in products]}")

    DATA.mkdir(exist_ok=True)
    sources = {}
    if SOURCES_FILE.exists():
        sources = json.loads(SOURCES_FILE.read_text(encoding="utf-8"))

    sources = run_discovery(products, sources, settings)
    SOURCES_FILE.write_text(json.dumps(sources, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    save_serpapi_quota()

    rates = get_fx_rates()
    offers = fetch_offers(products, sources, rates)
    today = date.today().isoformat()
    rows = append_history(offers, products, today)
    build_excel(rows, products)

    from dashboard import build_dashboard
    out = build_dashboard(rows, products, settings, today)
    log(f"[DASHBOARD] Zapisano {out}")
    log("Gotowe.")
    save_run_log()
    return 0


if __name__ == "__main__":
    sys.exit(main())
