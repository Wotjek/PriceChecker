"""Generator dashboardu HTML v2 - centrum dowodzenia (SPA)."""

import csv
import json
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).parent
OUTPUT = ROOT / "output"
OFFERS_CSV = ROOT / "data" / "all_offers.csv"
QUOTA_FILE = ROOT / "data" / "serpapi_quota.json"
SERPER_QUOTA_FILE = ROOT / "data" / "serper_quota.json"
RUNLOG_FILE = ROOT / "data" / "last_run.log"
DOCS = ROOT / "docs"           # kopia dashboardu dla GitHub Pages
WORKFLOW_FILE = "price-tracker.yml"
OFFERS_EMBED_DAYS = 120   # ile dni pelnego audytu ofert osadzac w HTML
RUNLOG_EMBED_LINES = 600  # ile ostatnich linii logu osadzac (Diagnostyka)

TEMPLATE = r"""<!DOCTYPE html>
<html lang="pl">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Price Tracker — Centrum dowodzenia</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Barlow+Condensed:wght@500;600;700&family=Barlow:wght@400;500;600&family=JetBrains+Mono:wght@500;700&display=swap" rel="stylesheet">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/js-yaml/4.1.0/js-yaml.min.js"></script>
<style>
:root{
  --bg:#0E1216; --panel:#161C22; --panel2:#121820; --line:#26303A;
  --ink:#E9EEF2; --muted:#8B98A5; --faint:#5A6672;
  --fire:#E8452F; --fire-press:#C4351F;
  --teal:#5FD3C4; --good:#46D39A; --bad:#F0A03C;
}
*{box-sizing:border-box;margin:0;padding:0}
html{background:var(--bg)}
body{font-family:'Barlow',sans-serif;color:var(--ink);min-height:100vh;
  background:radial-gradient(1200px 500px at 70% -10%, rgba(95,211,196,.06), transparent 60%),var(--bg);
  padding:24px clamp(14px,4vw,48px) 64px}
a{color:var(--teal);text-decoration:none} a:hover{text-decoration:underline}
.mono{font-family:'JetBrains Mono',monospace}
.disp{font-family:'Barlow Condensed',sans-serif;text-transform:uppercase;letter-spacing:.08em}

header{display:flex;align-items:center;gap:18px;flex-wrap:wrap;
  border-bottom:1px solid var(--line);padding-bottom:14px}
h1{font-family:'Barlow Condensed';font-weight:700;font-size:28px;text-transform:uppercase;
  letter-spacing:.1em;line-height:1}
h1 small{display:block;font-size:11px;font-weight:500;color:var(--muted);letter-spacing:.2em;margin-top:5px}
.spacer{flex:1}
.status{display:flex;flex-direction:column;align-items:flex-end;gap:2px;font-size:13px;color:var(--muted)}
.statusline{display:flex;align-items:center;gap:8px}
.led{width:10px;height:10px;border-radius:50%;background:var(--faint);flex:none}
.led.ok{background:var(--good);box-shadow:0 0 8px rgba(70,211,154,.7)}
.led.run{background:var(--bad);box-shadow:0 0 8px rgba(240,160,60,.8);animation:pulse 1.1s ease-in-out infinite}
.led.err{background:var(--fire);box-shadow:0 0 8px rgba(232,69,47,.7)}
.lastok{font-size:11px;color:var(--faint)}
@keyframes pulse{50%{opacity:.35}}
@media (prefers-reduced-motion:reduce){.led.run{animation:none}}

button{font-family:'Barlow Condensed';text-transform:uppercase;letter-spacing:.12em;
  font-weight:700;cursor:pointer;border:0;border-radius:6px;color:var(--ink)}
#fireBtn{background:var(--fire);color:#fff;font-size:16px;padding:11px 24px;
  box-shadow:0 3px 0 var(--fire-press), inset 0 1px 0 rgba(255,255,255,.25);transition:transform .05s}
#fireBtn:active{transform:translateY(2px);box-shadow:0 1px 0 var(--fire-press)}
#fireBtn:disabled{background:#3a4148;box-shadow:none;color:var(--muted);cursor:default}
#lightBtn{background:transparent;color:var(--teal);font-size:14px;padding:10px 18px;
  border:1px solid var(--teal);transition:transform .05s}
#lightBtn:hover{background:rgba(95,211,196,.08)}
#lightBtn:active{transform:translateY(2px)}
#lightBtn:disabled{border-color:var(--line);color:var(--muted);cursor:default;background:transparent}
.ghost{background:transparent;color:var(--muted);font-size:12px;border:1px solid var(--line)!important;padding:9px 14px}
.ghost:hover{color:var(--ink);border-color:var(--faint)!important}

nav{display:flex;gap:4px;flex-wrap:wrap;margin:16px 0 22px;border-bottom:1px solid var(--line)}
nav button{background:none;color:var(--muted);font-size:15px;padding:10px 16px;border-radius:0;
  border-bottom:2px solid transparent!important;letter-spacing:.1em}
nav button.on{color:var(--ink);border-bottom-color:var(--teal)!important}
nav button:hover{color:var(--ink)}

.panelbox{background:linear-gradient(180deg,var(--panel),var(--panel2));
  border:1px solid var(--line);border-radius:10px;padding:20px}

/* karuzela */
.carousel{display:flex;align-items:stretch;gap:10px}
.arrow{background:var(--panel);border:1px solid var(--line)!important;color:var(--muted);
  font-size:26px;width:44px;border-radius:10px;flex:none}
.arrow:hover{color:var(--ink)}
.stage{flex:1;min-width:0}
.stagehead{display:flex;align-items:baseline;gap:14px;flex-wrap:wrap;margin-bottom:6px}
.stagehead h2{font-family:'Barlow Condensed';font-weight:600;font-size:24px;text-transform:uppercase;letter-spacing:.08em}
.stagehead .code{color:var(--faint);font-size:13px}
.buy{background:rgba(70,211,154,.15);color:var(--good);border:1px solid rgba(70,211,154,.4);
  border-radius:4px;padding:2px 10px;font-size:13px;font-weight:600;letter-spacing:.08em}
.periods{display:flex;gap:6px;margin:8px 0 4px}
.periods button{background:none;border:1px solid var(--line)!important;color:var(--muted);
  font-size:12px;padding:5px 12px}
.periods button.on{color:var(--bg);background:var(--teal);border-color:var(--teal)!important}
.bigchart{height:290px;margin-top:6px}
.stagemeta{display:flex;gap:26px;flex-wrap:wrap;margin-top:12px;font-size:13px;color:var(--muted)}
.stagemeta b{color:var(--ink);font-family:'JetBrains Mono';font-weight:600}
.dots{display:flex;justify-content:center;gap:8px;margin-top:14px}
.dot{width:8px;height:8px;border-radius:50%;background:var(--line);cursor:pointer}
.dot.on{background:var(--teal)}

/* statystyki produktu */
.chips{display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px;margin-bottom:18px}
.chip{background:var(--panel2);border:1px solid var(--line);border-radius:8px;padding:12px 14px}
.chip .lbl{font-size:11px;color:var(--faint);letter-spacing:.16em;text-transform:uppercase;font-family:'Barlow Condensed'}
.chip .val{font-family:'JetBrains Mono';font-size:20px;font-weight:700;margin-top:4px}
.chip .sub{font-size:11px;color:var(--muted);margin-top:2px}
.chip.hot .val{color:var(--good)}

.quota{display:flex;align-items:center;gap:14px;margin-top:14px;padding:12px 16px;
  background:var(--panel2);border:1px solid var(--line);border-radius:8px;font-size:13px;color:var(--muted)}
.quota .lbl{font-family:'Barlow Condensed';text-transform:uppercase;letter-spacing:.14em;
  font-size:12px;color:var(--faint);flex:none}
.qbar{flex:1;height:8px;background:var(--line);border-radius:4px;overflow:hidden;min-width:120px}
.qbar>div{height:100%;background:var(--teal);border-radius:4px}
.qbar.low>div{background:var(--bad)}
.quota b{color:var(--ink);font-family:'JetBrains Mono'}
section.offers{margin-top:34px}
h3.sect{font-family:'Barlow Condensed';font-weight:600;font-size:19px;text-transform:uppercase;
  letter-spacing:.12em;color:var(--muted);margin:26px 0 12px}
table{width:100%;border-collapse:collapse;font-size:14px}
th{font-family:'Barlow Condensed';text-transform:uppercase;letter-spacing:.1em;font-weight:600;
  font-size:12px;color:var(--faint);text-align:left;padding:8px 12px;border-bottom:1px solid var(--line)}
td{padding:9px 12px;border-bottom:1px solid rgba(38,48,58,.5)}
td.num{font-family:'JetBrains Mono';font-weight:500}
tr.best td{background:rgba(70,211,154,.10)}
tr.best td:first-child{border-left:3px solid var(--good)}
tr.best td.num{color:var(--good)}
tr.rowlink{cursor:pointer}
tr.rowlink:hover td{background:rgba(95,211,196,.09)}
.pill{font-size:12px;color:var(--faint)}
.tagbest{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:4px;font-size:10px;
  font-family:'Barlow Condensed';letter-spacing:.12em;text-transform:uppercase;font-weight:700;
  background:rgba(70,211,154,.15);color:var(--good);border:1px solid rgba(70,211,154,.4)}
.pctup{font-size:11px;color:var(--faint);font-family:'JetBrains Mono'}
.tagvia{display:inline-block;margin-left:8px;padding:1px 8px;border-radius:4px;font-size:10px;
  font-family:'Barlow Condensed';letter-spacing:.12em;text-transform:uppercase;font-weight:700;
  background:rgba(95,160,255,.13);color:var(--accent2,#7ab3ff);border:1px solid rgba(95,160,255,.35)}
.up{color:var(--bad)} .down{color:var(--good)}
.avail-ok{color:var(--good)} .avail-no{color:var(--fire)}
th.sortable{cursor:pointer;user-select:none}
th.sortable:hover{color:var(--ink)}
.range{position:relative;height:4px;background:var(--line);border-radius:2px;min-width:80px;max-width:110px;margin:6px 0}
.range i{position:absolute;top:-3px;width:10px;height:10px;border-radius:50%;transform:translateX(-50%)}
.stalebadge{display:inline-block;margin-left:6px;padding:0 6px;border-radius:4px;font-size:10px;vertical-align:2px;
  font-family:'Barlow Condensed';letter-spacing:.1em;text-transform:uppercase;
  background:rgba(240,160,60,.12);color:var(--bad);border:1px solid rgba(240,160,60,.35)}

/* konfiguracja */
.cfgcard{border:1px solid var(--line);border-radius:10px;padding:16px;margin-bottom:14px;background:var(--panel2)}
.cfgrow{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin-bottom:10px}
label{font-size:11px;color:var(--faint);letter-spacing:.14em;text-transform:uppercase;
  font-family:'Barlow Condensed';display:block;margin-bottom:4px}
input[type=text],textarea{width:100%;background:var(--bg);border:1px solid var(--line);border-radius:6px;
  color:var(--ink);font-family:'JetBrains Mono';font-size:13px;padding:8px 10px}
textarea{min-height:56px;resize:vertical}
input:focus,textarea:focus{outline:none;border-color:var(--teal)}
.check{display:flex;align-items:center;gap:8px;font-size:13px;color:var(--muted);margin-top:20px}
.cfgtop{display:flex;justify-content:space-between;align-items:center;margin-bottom:10px}
.del{background:none;color:var(--fire);font-size:12px;border:1px solid rgba(232,69,47,.4)!important;padding:6px 12px}
.cfgactions{display:flex;gap:10px;margin-top:16px;flex-wrap:wrap}
.save{background:var(--teal);color:var(--bg);font-size:15px;padding:11px 24px}
.note{font-size:12px;color:var(--faint);margin-top:10px;line-height:1.6}

/* diagnostyka */
.logbox{font-family:'JetBrains Mono',monospace;font-size:12px;line-height:1.75;
  white-space:pre;overflow:auto;max-height:68vh}
.ll{color:var(--muted)} .ll-info{color:var(--ink)} .ll-ok{color:var(--good)}
.ll-http{color:var(--fire)} .ll-noprice{color:var(--bad)}
.ll-skip{color:var(--faint)} .ll-crawl{color:var(--teal)}
.logchip{cursor:pointer} .logchip:hover{border-color:var(--faint)}
.logchip.onf{border-color:var(--teal)}
.lv-ok{color:var(--good)} .lv-http{color:var(--fire)} .lv-noprice{color:var(--bad)}
.lv-skip{color:var(--muted)} .lv-crawl{color:var(--teal)}

#toast{position:fixed;bottom:22px;left:50%;transform:translateX(-50%);background:var(--panel);
  border:1px solid var(--line);border-radius:8px;padding:12px 20px;font-size:14px;opacity:0;
  pointer-events:none;transition:opacity .25s;max-width:90vw;z-index:9}
#toast.show{opacity:1}
footer{margin-top:44px;font-size:12px;color:var(--faint)}
.emptybig{color:var(--faint);text-align:center;padding:60px 0;font-size:15px}
</style>
</head>
<body>

<header>
  <h1>Price&nbsp;Tracker<small>Centrum dowodzenia</small></h1>
  <div class="spacer"></div>
  <div class="status">
    <div class="statusline"><span class="led ok" id="led"></span><span id="statusTxt">—</span></div>
    <span class="lastok" id="lastRun"></span>
  </div>
  <button class="ghost" id="refreshBtn">Odśwież dane</button>
  <button class="ghost" id="tokenBtn">Token</button>
  <button id="lightBtn" class="disp" title="Tylko monitoring znanych sklepów — nie zużywa limitu SerpAPI">▶ Light Fire</button>
  <button id="fireBtn" class="disp" title="Pełne discovery (szuka nowych sklepów) + monitoring — zużywa limit SerpAPI">▶ Fire</button>
</header>

<nav id="nav"></nav>
<main id="view"></main>

<footer>Dane: <span class="mono" id="genInfo"></span> · najniższa oferta oznaczona paskiem
· FIRE uruchamia workflow w GitHub Actions; po zakończeniu dane odświeżą się same</footer>
<div id="toast"></div>

<script>
const DATA = __DATA__;
const WORKFLOW = "__WORKFLOW__";
const PERIODS = [["T",7],["M",30],["K",91],["MAX",0]];
const SHOP_COLORS = ["#5FD3C4","#F0A03C","#8FA9FF","#E77FB3","#A6E06B","#FF8F6B","#6BC7FF","#D6B25F"];
let state = {
  history: DATA.history, offers: DATA.offers, runlog: DATA.runlog||[],
  tab: "home", idx: 0, period: {home:"M"}, charts: [],
  cfg: null, cfgSha: null,
};
const $ = id => document.getElementById(id);
const pln = new Intl.NumberFormat('pl-PL',{style:'currency',currency:'PLN'});
const toast = m => { const t=$('toast'); t.textContent=m; t.classList.add('show');
  setTimeout(()=>t.classList.remove('show'), 4500); };
const esc = s => String(s??'').replace(/[&<>"']/g, c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));

function tokenSilent(){ return (localStorage.getItem('pt_token')||'').trim(); }
function getToken(force){
  let tok = tokenSilent();
  if (!tok || force){
    tok = prompt('Wklej GitHub token (fine-grained, tylko to repo, uprawnienia: Contents RW + Actions RW).\nZapisany będzie wyłącznie w tej przeglądarce.', tok) || '';
    if (tok) localStorage.setItem('pt_token', tok.trim());
  }
  return tokenSilent();
}
const gh = (path, opts={}) => fetch('https://api.github.com'+path, {...opts,
  headers:{'Accept':'application/vnd.github+json','Authorization':'Bearer '+tokenSilent(),
           ...(opts.headers||{})}});

const byKey = (list,key)=>{const m={};for(const r of list)(m[r[key]] ||= []).push(r);return m;};
const cutoff = code => { const d = (PERIODS.find(p=>p[0]===code)||[])[1]||0;
  if(!d) return ''; const t=new Date(); t.setDate(t.getDate()-d); return t.toISOString().slice(0,10); };
function killCharts(){ state.charts.forEach(c=>c.destroy()); state.charts=[]; }
function setStatus(cls,txt){ $('led').className='led '+cls; $('statusTxt').textContent=txt; }

/* ================= NAV ================= */
function renderNav(){
  // stale 4 zakladki - szczegoly produktu otwiera sie z tabeli w "Produkty"
  const items = [["home","Główna"], ["list","Produkty"],
    ["diag","Diagnostyka"], ["cfg","Konfiguracja"]];
  const isProd = !['home','list','diag','cfg'].includes(state.tab);
  $('nav').innerHTML = items.map(([k,l])=>
    `<button class="disp ${state.tab===k||(k==='list'&&isProd)?'on':''}" data-tab="${esc(k)}">${esc(l)}</button>`).join('');
  $('nav').querySelectorAll('button').forEach(b=> b.onclick = ()=>{
    state.tab=b.dataset.tab; render(); if(state.tab==='cfg') loadConfig(); });
}

/* ================= GŁÓWNA ================= */
function periodButtons(scope){
  return `<div class="periods">` + PERIODS.map(([c])=>
    `<button data-p="${c}" data-s="${scope}" class="${(state.period[scope]||'M')===c?'on':''}">${
      {T:'Tydzień',M:'Miesiąc',K:'Kwartał',MAX:'Max'}[c]}</button>`).join('') + `</div>`;
}
function bindPeriods(el){
  el.querySelectorAll('.periods button').forEach(b=> b.onclick = ()=>{
    state.period[b.dataset.s]=b.dataset.p; render(); });
}

function renderHome(el){
  const products = DATA.products;
  if (!products.length){ el.innerHTML = '<div class="emptybig">Dodaj produkty w zakładce Konfiguracja</div>'; return; }
  state.idx = ((state.idx % products.length) + products.length) % products.length;
  const p = products[state.idx];
  const hist = (byKey(state.history,'product_id')[p.id]||[]).slice().sort((a,b)=>a.date<b.date?-1:1);
  const from = cutoff(state.period.home||'M');
  const rows = hist.filter(r=>r.date>=from);
  const last = hist[hist.length-1];
  const min = rows.length ? rows.reduce((a,b)=>+a.price_pln<=+b.price_pln?a:b) : null;
  const target = p.target_pln ? +p.target_pln : 0;
  const buy = target && last && +last.price_pln <= target;

  el.innerHTML = `
  <div class="panelbox">
    <div class="carousel">
      <button class="arrow" id="prev" aria-label="Poprzedni produkt">‹</button>
      <div class="stage">
        <div class="stagehead">
          <h2>${esc(p.name)}</h2><span class="code mono">${esc(p.id)}${p.worldwide?' · WORLDWIDE':''}</span>
          ${buy?'<span class="buy">● KUP — cena docelowa osiągnięta</span>':''}
        </div>
        ${periodButtons('home')}
        <div class="bigchart"><canvas id="homeChart"></canvas></div>
        <div class="stagemeta">
          ${last?`<span>Aktualnie: <b>${pln.format(+last.price_pln)}</b> · <a href="${esc(last.url)}" target="_blank" rel="noopener">${esc(last.shop)}</a> (${esc(last.date)})</span>`:'<span>Brak pomiarów</span>'}
          ${min?`<span>Min. okresu: <b>${pln.format(+min.price_pln)}</b> (${esc(min.date)})</span>`:''}
          ${target?`<span>Cena docelowa: <b>${pln.format(target)}</b></span>`:''}
        </div>
      </div>
      <button class="arrow" id="next" aria-label="Następny produkt">›</button>
    </div>
    <div class="dots">${products.map((_,i)=>`<span class="dot ${i===state.idx?'on':''}" data-i="${i}"></span>`).join('')}</div>
  </div>
  ${quotaWidget()}
  <section class="offers"><h3 class="sect">Wszystkie dzisiejsze oferty <span class="pill" id="offersDate"></span></h3>
  <div id="offersTables"></div></section>`;

  $('prev').onclick = ()=>{state.idx--; render();};
  $('next').onclick = ()=>{state.idx++; render();};
  el.querySelectorAll('.dot').forEach(d=> d.onclick = ()=>{state.idx=+d.dataset.i; render();});
  bindPeriods(el);
  document.onkeydown = e=>{ if(state.tab!=='home')return;
    if(e.key==='ArrowLeft'){state.idx--;render();} if(e.key==='ArrowRight'){state.idx++;render();} };

  if (rows.length){
    state.charts.push(new Chart($('homeChart'),{type:'line',
      data:{labels:rows.map(r=>r.date.slice(5)),
        datasets:[{data:rows.map(r=>+r.price_pln),borderColor:'#5FD3C4',borderWidth:2,
          pointRadius:rows.length>40?0:3,pointHitRadius:12,pointBackgroundColor:'#5FD3C4',
          fill:true,backgroundColor:'rgba(95,211,196,.12)',tension:0}]},
      options:{responsive:true,maintainAspectRatio:false,
        plugins:{legend:{display:false},
          tooltip:{callbacks:{
            title:i=>rows[i[0].dataIndex].date,
            label:i=>` ${pln.format(i.parsed.y)} · ${rows[i.dataIndex].shop}`}}},
        scales:{x:{ticks:{color:'#5A6672',maxTicksLimit:9,font:{size:10}},grid:{display:false}},
          y:{ticks:{color:'#5A6672',font:{family:'JetBrains Mono',size:10},callback:v=>v.toLocaleString('pl-PL')},
             grid:{color:'rgba(38,48,58,.6)'}}}}}));
  }
  renderOffersTables($('offersTables'), DATA.products);
}

function quotaWidget(){
  const bar = (lbl, left, total, used, info, checked) => {
    const pct = total ? Math.max(0, Math.min(100, left/total*100)) : 0;
    return `<div class="quota">
    <span class="lbl">${lbl}</span>
    <div class="qbar ${pct<20?'low':''}"><div style="width:${pct.toFixed(0)}%"></div></div>
    <span>pozostało <b>${left}</b> z <b>${total}</b> ${info} · stan z ${esc(checked||'')}</span>
  </div>`;};
  let html='';
  const q = DATA.serpapi;
  if(q && q.per_month) html += bar('Limit SerpAPI', +q.left||0, +q.per_month||0, +q.used||0,
    `darmowych zapytań (zużyte: ${+q.used||0})`, q.checked);
  const s = DATA.serper;
  if(s && s.total) html += bar('Kredyty Serper', +s.left||0, +s.total||0, +s.used||0,
    `kredytów (zużyte: ${+s.used||0}, licznik lokalny)`, s.checked);
  return html;
}
function renderOffersTables(wrap, products){
  const dates = state.offers.map(o=>o.date).sort();
  const lastDate = dates[dates.length-1]||'';
  const d = $('offersDate'); if(d) d.textContent = lastDate?('· '+lastDate):'';
  const todays = byKey(state.offers.filter(o=>o.date===lastDate),'product_id');
  wrap.innerHTML='';
  for (const p of products){
    const rows=(todays[p.id]||[]).sort((a,b)=>+a.price_pln-+b.price_pln);
    if(!rows.length) continue;
    let html=`<table><thead><tr><th>${esc(p.name)}</th><th>Cena</th><th>PLN</th><th>Dostępność</th><th>Link</th></tr></thead><tbody>`;
    const best = +rows[0].price_pln;
    rows.forEach(o=>{
      const isBest = +o.price_pln <= best + 0.001;
      const diff = best ? (+o.price_pln - best) / best * 100 : 0;
      html+=`<tr class="${isBest?'best':''}">
      <td>${esc(o.domain)}${isBest?'<span class="tagbest">najtaniej</span>':''}${o.via?`<span class="tagvia" title="${o.via==='shopping'?'cena z feedu Google Shopping (sklep blokuje boty)':'cena z indeksu Google — może być sprzed kilku dni'}">Google</span>`:''}</td>
      <td class="num">${(+o.price).toLocaleString('pl-PL')} ${esc(o.currency)}</td>
      <td class="num">${pln.format(+o.price_pln)}${isBest?'':` <span class="pctup">+${diff.toFixed(1).replace('.',',')}%</span>`}</td>
      <td class="pill ${/instock|dostepn/i.test(o.availability)?'avail-ok':'avail-no'}">${esc(o.availability)}</td>
      <td><a href="${esc(o.url)}" target="_blank" rel="noopener">otwórz →</a></td></tr>`;});
    wrap.insertAdjacentHTML('beforeend', html+'</tbody></table><br>');
  }
  if(!wrap.innerHTML) wrap.innerHTML='<div class="emptybig">Brak ofert — uruchom FIRE</div>';
}

/* ================= PRODUKTY (przegląd) ================= */
function renderList(el){
  const products = DATA.products;
  if(!products.length){ el.innerHTML='<div class="emptybig">Dodaj produkty w zakładce Konfiguracja</div>'; return; }
  const hist = byKey(state.history,'product_id');
  const offersBy = byKey(state.offers,'product_id');

  const items = products.map(p=>{
    const h=(hist[p.id]||[]).slice().sort((a,b)=>a.date<b.date?-1:1);
    const last=h[h.length-1];
    const prev=h.length>1?h[h.length-2]:null;
    const min=h.length?h.reduce((a,b)=>+a.price_pln<=+b.price_pln?a:b):null;
    const max=h.length?h.reduce((a,b)=>+a.price_pln>=+b.price_pln?a:b):null;
    const offs=offersBy[p.id]||[];
    const lastOfferDate=offs.length?offs.map(o=>o.date).sort().pop():'';
    const shops=lastOfferDate?new Set(offs.filter(o=>o.date===lastOfferDate).map(o=>o.domain)).size:0;
    const target=p.target_pln?+p.target_pln:0;
    const buy=target&&last&&+last.price_pln<=target;
    const atMin=!!(last&&min&&+last.price_pln<=+min.price_pln+0.001);
    const vsMin=(last&&min&&!atMin)?((+last.price_pln-+min.price_pln)/+min.price_pln*100):0;
    const dd=(last&&prev)?((+last.price_pln-+prev.price_pln)/+prev.price_pln*100):0;
    const staleDays=last?Math.floor((Date.now()-new Date(last.date+'T12:00:00'))/864e5):0;
    return {p,last,prev,min,max,shops,buy,atMin,vsMin,dd,staleDays};
  });

  const s = state.listSort || {key:'name',dir:1};
  const keyFns = {
    name: r=>r.p.name.toLowerCase(),
    cur:  r=>r.last?+r.last.price_pln:Infinity,
    vsmin:r=>(r.last&&r.min)?(r.atMin?0:r.vsMin):Infinity,
    min:  r=>r.min?+r.min.price_pln:Infinity,
    shops:r=>r.shops
  };
  const fn = keyFns[s.key]||keyFns.name;
  items.sort((a,b)=>{const x=fn(a),y=fn(b);return (x<y?-1:x>y?1:0)*s.dir;});

  const TH=(key,label)=>`<th class="sortable" data-k="${key}" title="Kliknij, żeby sortować">${label}${s.key===key?(s.dir>0?' ▲':' ▼'):''}</th>`;
  let html = `<div class="panelbox"><h3 class="sect" style="margin-top:0">Wszystkie produkty
      <span class="pill">· kliknij wiersz, żeby zobaczyć szczegóły · kliknij nagłówek, żeby sortować</span></h3>
    <table><thead><tr>${TH('name','Produkt')}${TH('cur','Aktualnie (PLN)')}${TH('vsmin','vs min')}
      <th title="Pozycja aktualnej ceny między minimum a maksimum historycznym">Zakres min–max</th>
      ${TH('min','Min. historyczne')}${TH('shops','Sklepy')}<th>Sklep</th><th></th></tr></thead><tbody>`;

  for(const r of items){
    const {p,last,prev,min,max,shops,buy,atMin,vsMin,dd,staleDays}=r;
    const trend=(prev&&Math.abs(dd)>=0.05)?` · <span class="${dd>0?'up':'down'}">${dd>0?'▲':'▼'} ${Math.abs(dd).toFixed(1).replace('.',',')}%</span>`:'';
    const stale=(last&&staleDays>=2)?` <span class="stalebadge" title="Ostatni pomiar jest starszy niż 2 dni">sprzed ${staleDays} dni</span>`:'';
    const hlen=(hist[p.id]||[]).length;
    const spreadOk=last&&min&&max&&(+max.price_pln-+min.price_pln)>=Math.max(0.01,+min.price_pln*0.01);
    let range;
    if(hlen<7){
      range=`<span style="color:var(--faint);font-size:11px" title="Pasek pojawi się po min. 7 pomiarach — przy ${hlen} pomiarach aktualna cena jest zawsze na skraju zakresu">za mało historii (${hlen})</span>`;
    }else if(!spreadOk){
      range=`<span style="color:var(--faint);font-size:11px" title="Rozpiętość min–max poniżej 1% — cena się nie zmienia">cena stabilna</span>`;
    }else{
      const pct=Math.max(0,Math.min(100,(+last.price_pln-+min.price_pln)/(+max.price_pln-+min.price_pln)*100));
      const col=pct<=15?'var(--good)':pct>=85?'var(--bad)':'var(--teal)';
      range=`<div class="range" title="min ${pln.format(+min.price_pln)} · max ${pln.format(+max.price_pln)} · aktualna w ${pct.toFixed(0)}% zakresu"><i style="left:${pct}%;background:${col}"></i></div>`;
    }
    html+=`<tr class="rowlink ${buy?'best':''}" data-pid="${esc(p.id)}">
      <td><b>${esc(p.name)}</b>${buy?' <span class="buy">● KUP</span>':''}<br><span class="mono" style="color:var(--faint);font-size:11px">${esc(p.id)}${p.worldwide?' · WW':''}</span></td>
      <td class="num">${last?pln.format(+last.price_pln):'—'}${stale}${last?`<br><span style="color:var(--faint);font-size:11px">${esc(last.date)}${trend}</span>`:''}</td>
      <td class="num">${!last||!min?'—':atMin?'<span class="down" title="Aktualna cena równa minimum historycznemu">● = min</span>':`<span class="up" title="O tyle drożej niż minimum historyczne">▲ +${vsMin.toFixed(1).replace('.',',')}%</span>`}</td>
      <td>${range}</td>
      <td class="num">${min?pln.format(+min.price_pln):'—'}${min?`<br><span style="color:var(--faint);font-size:11px">${esc(min.date)}</span>`:''}</td>
      <td class="num">${shops||'—'}${shops===1?' <span class="up" title="Tylko jeden sklep z ofertą — słabe pokrycie">!</span>':''}</td>
      <td>${last?`<a href="${esc(last.url)}" target="_blank" rel="noopener" onclick="event.stopPropagation()">${esc(last.shop)} →</a>`:'—'}</td>
      <td style="color:var(--faint)">›</td></tr>`;
  }
  el.innerHTML = html+'</tbody></table></div>';
  el.querySelectorAll('.rowlink').forEach(r=> r.onclick=()=>{ state.tab=r.dataset.pid; render(); });
  el.querySelectorAll('th.sortable').forEach(t=> t.onclick=()=>{
    const k=t.dataset.k;
    state.listSort = (s.key===k)?{key:k,dir:-s.dir}:{key:k,dir:1};
    render();
  });
}

/* ================= ZAKŁADKA PRODUKTU ================= */
function renderProduct(el, pid){
  const p = DATA.products.find(x=>x.id===pid); if(!p){el.innerHTML='';return;}
  const scope='p_'+pid;
  const from = cutoff(state.period[scope]||'M');
  const hist=(byKey(state.history,'product_id')[pid]||[]).slice().sort((a,b)=>a.date<b.date?-1:1);
  const offers=(byKey(state.offers,'product_id')[pid]||[]).filter(o=>o.date>=from);
  const histP = hist.filter(r=>r.date>=from);
  const last = hist[hist.length-1];
  const minAll = hist.length?hist.reduce((a,b)=>+a.price_pln<=+b.price_pln?a:b):null;
  const avg = histP.length?histP.reduce((s,r)=>s+ +r.price_pln,0)/histP.length:0;
  const shops = [...new Set(offers.map(o=>o.domain))].sort();
  const vsAvg = (last&&avg)?((+last.price_pln-avg)/avg*100):0;

  el.innerHTML = `
  <div class="stagehead" style="margin-bottom:14px">
    <button class="ghost" id="backList" style="margin-right:4px">← Produkty</button>
    <h2>${esc(p.name)}</h2><span class="code mono">${esc(pid)}${p.worldwide?' · WORLDWIDE':''}</span>
  </div>
  <div class="chips">
    <div class="chip ${last&&minAll&&+last.price_pln<=+minAll.price_pln+0.001?'hot':''}">
      <div class="lbl">Aktualna najniższa</div>
      <div class="val">${last?pln.format(+last.price_pln):'—'}</div>
      <div class="sub">${last?esc(last.shop)+' · '+esc(last.date):''}</div></div>
    <div class="chip"><div class="lbl">Minimum (cała historia)</div>
      <div class="val">${minAll?pln.format(+minAll.price_pln):'—'}</div>
      <div class="sub">${minAll?esc(minAll.date)+' · '+esc(minAll.shop):''}</div></div>
    <div class="chip"><div class="lbl">Średnia okresu</div>
      <div class="val">${avg?pln.format(avg):'—'}</div>
      <div class="sub">${avg?(vsAvg<=0?'aktualnie ':'aktualnie +')+vsAvg.toFixed(1)+'% vs średnia':''}</div></div>
    <div class="chip"><div class="lbl">Sklepów w okresie</div>
      <div class="val">${shops.length}</div>
      <div class="sub">${p.target_pln?('cel: '+pln.format(+p.target_pln)):''}</div></div>
  </div>
  <div class="panelbox">
    ${periodButtons(scope)}
    <div class="bigchart"><canvas id="prodChart"></canvas></div>
  </div>
  <h3 class="sect">Ostatnie oferty (wszystkie sklepy)</h3><div id="prodOffers"></div>
  <h3 class="sect">Historia dziennych minimów</h3><div id="prodHist"></div>`;
  $('backList').onclick = ()=>{ state.tab='list'; render(); };
  bindPeriods(el);

  // wykres: linia per sklep (z audytu ofert); gdy brak audytu - dzienne minima
  const labels = [...new Set(offers.map(o=>o.date).concat(histP.map(r=>r.date)))].sort();
  const datasets = shops.map((s,i)=>{
    const m = Object.fromEntries(offers.filter(o=>o.domain===s).map(o=>[o.date,+o.price_pln]));
    return {label:s, data:labels.map(d=>m[d]??null), borderColor:SHOP_COLORS[i%SHOP_COLORS.length],
      borderWidth:1.6, pointRadius:labels.length>40?0:2.5, spanGaps:true, tension:0};});
  if (!datasets.length && histP.length){
    const m = Object.fromEntries(histP.map(r=>[r.date,+r.price_pln]));
    datasets.push({label:'dzienny min', data:labels.map(d=>m[d]??null),
      borderColor:'#5FD3C4', borderWidth:2.4, pointRadius:0, spanGaps:true, tension:0});
  }
  if (labels.length){
    state.charts.push(new Chart($('prodChart'),{type:'line',
      data:{labels:labels.map(d=>d.slice(5)),datasets},
      options:{responsive:true,maintainAspectRatio:false,interaction:{mode:'nearest',intersect:false},
        plugins:{legend:{labels:{color:'#8B98A5',boxWidth:14,font:{size:11}}},
          tooltip:{callbacks:{title:i=>labels[i[0].dataIndex],
            label:i=>` ${i.dataset.label}: ${pln.format(i.parsed.y)}`}}},
        scales:{x:{ticks:{color:'#5A6672',maxTicksLimit:9,font:{size:10}},grid:{display:false}},
          y:{ticks:{color:'#5A6672',font:{family:'JetBrains Mono',size:10},callback:v=>v.toLocaleString('pl-PL')},
             grid:{color:'rgba(38,48,58,.6)'}}}}}));
  } else document.querySelector('#view .panelbox').innerHTML='<div class="emptybig">Brak danych w tym okresie</div>';

  renderOffersTables($('prodOffers'), [p]);
  const h=$('prodHist');
  if(histP.length){
    let html=`<table><thead><tr><th>Data</th><th>Najniższa (PLN)</th><th>Oryginalnie</th><th>Sklep</th><th>Ofert</th><th>Link</th></tr></thead><tbody>`;
    histP.slice().reverse().forEach(r=>{html+=`<tr><td class="num">${esc(r.date)}</td>
      <td class="num">${pln.format(+r.price_pln)}</td>
      <td class="num">${(+r.price_orig).toLocaleString('pl-PL')} ${esc(r.currency)}</td>
      <td>${esc(r.shop)}</td><td class="pill">${esc(r.offers_checked||'')}</td>
      <td><a href="${esc(r.url)}" target="_blank" rel="noopener">otwórz →</a></td></tr>`;});
    h.innerHTML=html+'</tbody></table>';
  } else h.innerHTML='<div class="emptybig">Brak historii w tym okresie</div>';
}

/* ================= DIAGNOSTYKA ================= */
const LOG_CATS = [
  ["ok",    "Oferty z ceną",  l=>/^\s*\+\s/.test(l)],
  ["http",  "Błędy HTTP / sieć", l=>/HTTP \d+|blad pobierania/.test(l)],
  ["noprice","Brak danych o cenie", l=>/brak danych o cenie/.test(l)],
  ["skip",  "Odfiltrowane",   l=>/pomijam|niedostepny|brak wariantu/.test(l)],
  ["crawl", "Auto-crawl",     l=>/^\s*~\s/.test(l)],
];
function classifyLog(l){ for(const [k,,fn] of LOG_CATS) if(fn(l)) return k; return 'info'; }
function renderDiag(el){
  const lines = state.runlog||[];
  if(!lines.length){
    el.innerHTML='<div class="emptybig">Brak logu ostatniego przebiegu — uruchom FIRE albo „Odśwież dane"</div>';
    return;
  }
  const cls = lines.map(classifyLog);
  const cnt = k => cls.filter(c=>c===k).length;
  const flt = state.logFilter||'';
  el.innerHTML = `
  <div class="chips">${LOG_CATS.map(([k,lbl])=>
    `<div class="chip logchip ${flt===k?'onf':''}" data-k="${k}">
      <div class="lbl">${lbl}</div><div class="val lv-${k}">${cnt(k)}</div>
    </div>`).join('')}</div>
  <div class="panelbox">
    <h3 class="sect" style="margin-top:0">Log ostatniego przebiegu
      ${flt?`<span class="pill">· filtr aktywny — kliknij kafelek ponownie, by wyłączyć</span>`:''}</h3>
    <div class="logbox">${lines.map((l,i)=> (!flt||cls[i]===flt)
      ?`<div class="ll ll-${cls[i]}">${esc(l)||'&nbsp;'}</div>`:'').join('')}</div>
  </div>`;
  el.querySelectorAll('.logchip').forEach(c=> c.onclick=()=>{
    state.logFilter = (state.logFilter===c.dataset.k)?'':c.dataset.k; render(); });
}

/* ================= KONFIGURACJA ================= */
function renderConfig(el){
  el.innerHTML = `<div class="panelbox" id="cfgBox">
    <div class="emptybig">${DATA.repo?'Ładowanie konfiguracji z repo…':'Uzupełnij settings.github_repo w products.yaml, żeby edytować konfigurację z panelu'}</div>
  </div>`;
}
async function loadConfig(){
  if(!DATA.repo) return;
  if(!getToken()){ $('cfgBox').innerHTML='<div class="emptybig">Potrzebny token (przycisk Token u góry)</div>'; return; }
  try{
    const r = await gh(`/repos/${DATA.repo}/contents/products.yaml?ref=${DATA.branch}`);
    if(!r.ok) throw new Error('HTTP '+r.status);
    const j = await r.json();
    const bytes = Uint8Array.from(atob(j.content.replace(/\n/g,'')),c=>c.charCodeAt(0));
    state.cfg = jsyaml.load(new TextDecoder().decode(bytes)) || {};
    if(!Array.isArray(state.cfg.products)) state.cfg.products = [];
    state.cfgSha = j.sha;
    drawConfigForm();
  }catch(e){ $('cfgBox').innerHTML=`<div class="emptybig">Błąd wczytania products.yaml: ${esc(e.message)}</div>`; }
}
const CFG_KNOWN = ['id','name','ean','target_pln','worldwide','queries','seed_urls','exclude_domains','variant','min_pln','max_pln','require_tokens'];
function productCard(p, i){
  const lines = a=>(a||[]).join('\n');
  const extra = Object.fromEntries(Object.entries(p).filter(([k])=>!CFG_KNOWN.includes(k)));
  return `<div class="cfgcard" data-i="${i}" data-extra="${esc(JSON.stringify(extra))}">
    <div class="cfgtop"><span class="disp" style="color:var(--faint);font-size:13px">Produkt</span>
      <button class="del" data-del="${i}">Usuń</button></div>
    <div class="cfgrow">
      <div><label>ID / kod</label><input type="text" class="f-id" value="${esc(p.id||'')}" placeholder="FM2797"></div>
      <div><label>Nazwa</label><input type="text" class="f-name" value="${esc(p.name||'')}"></div>
      <div><label>EAN / GTIN</label><input type="text" class="f-ean" value="${esc(p.ean||'')}"></div>
      <div><label>Cena docelowa (PLN)</label><input type="text" class="f-target" value="${esc(p.target_pln||'')}" placeholder="np. 9500"></div>
      <div><label>Wariant (np. rozmiar)</label><input type="text" class="f-var" value="${esc(p.variant||'')}" placeholder="np. 56"></div>
      <div class="check"><input type="checkbox" class="f-ww" id="ww${i}" ${p.worldwide?'checked':''}><label for="ww${i}" style="margin:0">worldwide (poza EU)</label></div>
    </div>
    <div class="cfgrow">
      <div><label>Min. cena (PLN, filtr szumu)</label><input type="text" class="f-min" value="${esc(p.min_pln||'')}" placeholder="np. 800"></div>
      <div><label>Max. cena (PLN, filtr szumu)</label><input type="text" class="f-max" value="${esc(p.max_pln||'')}" placeholder="np. 3000"></div>
      <div><label>Wymagane słowa (1/linia, "a|b" = a lub b)</label><textarea class="f-req">${esc(lines(p.require_tokens))}</textarea></div>
    </div>
    <div class="cfgrow">
      <div><label>Frazy wyszukiwania (1/linia)</label><textarea class="f-q">${esc(lines(p.queries))}</textarea></div>
      <div><label>Seed URLs (1/linia)</label><textarea class="f-seed">${esc(lines(p.seed_urls))}</textarea></div>
      <div><label>Wykluczone domeny (1/linia)</label><textarea class="f-ex">${esc(lines(p.exclude_domains))}</textarea></div>
    </div></div>`;
}
function drawConfigForm(){
  const prods = state.cfg.products;
  $('cfgBox').innerHTML = `
    <div id="cfgList">${prods.map((p,i)=>productCard(p,i)).join('')||'<div class="emptybig">Pusta lista — dodaj pierwszy produkt</div>'}</div>
    <div class="cfgactions">
      <button class="ghost" id="addProd">+ Dodaj produkt</button>
      <button class="save disp" id="saveCfg">Zapisz do repo</button>
      <button class="ghost" id="saveFire">Zapisz + Fire</button>
    </div>
    <p class="note">Zapis nadpisuje <span class="mono">products.yaml</span> w repo (komentarze w pliku zostaną utracone).
    To dokładnie ten plik, z którego korzysta workflow — zmiana listy wpływa na discovery i monitoring od kolejnego przebiegu.
    Po zapisie odpal FIRE, żeby od razu zebrać ceny dla nowej listy.</p>`;
  $('cfgList').querySelectorAll('.del').forEach(b=> b.onclick=()=>{
    collectConfig(); state.cfg.products.splice(+b.dataset.del,1); drawConfigForm(); });
  $('addProd').onclick = ()=>{ collectConfig(); state.cfg.products.push({}); drawConfigForm(); };
  $('saveCfg').onclick = ()=>saveConfig(false);
  $('saveFire').onclick = ()=>saveConfig(true);
}
function collectConfig(){
  const list=[...document.querySelectorAll('#cfgList .cfgcard')];
  const splitLines = v=>v.split('\n').map(s=>s.trim()).filter(Boolean);
  state.cfg.products = list.map(c=>{
    let p={};
    try{ p = JSON.parse(c.dataset.extra||'{}'); }catch(e){}
    p.id = c.querySelector('.f-id').value.trim();
    p.name = c.querySelector('.f-name').value.trim();
    const ean=c.querySelector('.f-ean').value.trim(); if(ean)p.ean=ean; else delete p.ean;
    const t=c.querySelector('.f-target').value.trim().replace(',','.'); if(t&&!isNaN(+t))p.target_pln=+t; else delete p.target_pln;
    const vv=c.querySelector('.f-var').value.trim(); if(vv)p.variant=vv; else delete p.variant;
    if(c.querySelector('.f-ww').checked)p.worldwide=true; else delete p.worldwide;
    const mn=c.querySelector('.f-min').value.trim().replace(',','.'); if(mn&&!isNaN(+mn))p.min_pln=+mn; else delete p.min_pln;
    const mx=c.querySelector('.f-max').value.trim().replace(',','.'); if(mx&&!isNaN(+mx))p.max_pln=+mx; else delete p.max_pln;
    const rq=splitLines(c.querySelector('.f-req').value); if(rq.length)p.require_tokens=rq; else delete p.require_tokens;
    const q=splitLines(c.querySelector('.f-q').value); if(q.length)p.queries=q; else delete p.queries;
    const s=splitLines(c.querySelector('.f-seed').value); if(s.length)p.seed_urls=s; else delete p.seed_urls;
    const x=splitLines(c.querySelector('.f-ex').value); if(x.length)p.exclude_domains=x; else delete p.exclude_domains;
    return p; }).filter(p=>p.id);
}
async function saveConfig(andFire){
  collectConfig();
  // zduplikowane ID scalaja bazy URL-i i mieszaja oferty roznych produktow
  const ids = state.cfg.products.map(p=>p.id);
  const dup = ids.find((id,i)=>ids.indexOf(id)!==i);
  if(dup){ toast('BŁĄD: zduplikowane ID "'+dup+'" — każdy produkt musi mieć unikalne ID'); return; }
  if(!state.cfg.settings) state.cfg.settings={github_repo:DATA.repo,branch:DATA.branch};
  const yamlTxt = "# Plik zarządzany także z dashboardu (zakładka Konfiguracja)\n" +
                  jsyaml.dump(state.cfg,{lineWidth:120,quotingType:'"'});
  const b64 = btoa(String.fromCharCode(...new TextEncoder().encode(yamlTxt)));
  try{
    const r = await gh(`/repos/${DATA.repo}/contents/products.yaml`,{method:'PUT',
      body:JSON.stringify({message:'Konfiguracja produktów z dashboardu',
        content:b64, sha:state.cfgSha, branch:DATA.branch})});
    if(!r.ok) throw new Error('HTTP '+r.status);
    state.cfgSha=(await r.json()).content.sha;
    toast(andFire?'Zapisano — odpalam FIRE':'Zapisano products.yaml w repo');
    if(andFire) fire();
  }catch(e){ toast('Błąd zapisu: '+e.message); }
}

/* ================= CSV / refresh / FIRE ================= */
function parseCSV(text){
  const rows=[];let row=[],cur='',q=false;
  for(let i=0;i<text.length;i++){const c=text[i];
    if(q){ if(c==='"'){ if(text[i+1]==='"'){cur+='"';i++;} else q=false;} else cur+=c; }
    else if(c==='"')q=true;
    else if(c===','){row.push(cur);cur='';}
    else if(c==='\n'||c==='\r'){ if(cur!==''||row.length){row.push(cur);rows.push(row);row=[];cur='';}
      if(c==='\r'&&text[i+1]==='\n')i++; }
    else cur+=c;}
  if(cur!==''||row.length){row.push(cur);rows.push(row);}
  const head=rows.shift()||[];
  return rows.map(r=>Object.fromEntries(head.map((h,i)=>[h,r[i]??''])));
}
async function fetchText(path){
  const r = await gh(`/repos/${DATA.repo}/contents/${path}?ref=${DATA.branch}`);
  if(!r.ok) throw new Error(path+': HTTP '+r.status);
  const j = await r.json();
  if (j.content) return new TextDecoder().decode(Uint8Array.from(atob(j.content.replace(/\n/g,'')),c=>c.charCodeAt(0)));
  const r2 = await fetch(j.download_url); return await r2.text(); // pliki >1MB
}
async function fetchCSV(path){ return parseCSV(await fetchText(path)); }
async function refresh(silent){
  if(!DATA.repo){ toast('Uzupełnij settings.github_repo w products.yaml'); return; }
  if(!getToken()) return;
  try{
    setStatus('run','Pobieram dane…');
    const [h,o]=await Promise.all([fetchCSV('data/history.csv'),fetchCSV('data/all_offers.csv')]);
    state.history=h; state.offers=o;
    try{ DATA.serpapi=JSON.parse(await fetchText('data/serpapi_quota.json')); }catch(e){}
    try{ DATA.serper=JSON.parse(await fetchText('data/serper_quota.json')); }catch(e){}
    try{ state.runlog=(await fetchText('data/last_run.log')).split('\n'); }catch(e){}
    try{ const cfg=jsyaml.load(await fetchText('products.yaml'))||{};
      if(Array.isArray(cfg.products)) DATA.products=cfg.products.filter(p=>p&&p.id)
        .map(p=>({id:p.id,name:p.name||p.id,worldwide:!!p.worldwide,target_pln:p.target_pln}));
    }catch(e){}
    render();
    setStatus('ok','Dane aktualne'); loadLastRun();
    if(!silent) toast('Dane odświeżone z GitHuba');
  }catch(e){ setStatus('err','Błąd odświeżania'); toast('Nie udało się pobrać danych: '+e.message); }
}
const lastHistDate = ()=> state.history.map(r=>r.date).sort().pop();
async function loadLastRun(){
  if(!DATA.repo || !tokenSilent()){
    $('lastRun').textContent = 'ostatni pomiar w danych: '+(lastHistDate()||'—'); return; }
  try{
    const r = await gh(`/repos/${DATA.repo}/actions/workflows/${WORKFLOW}/runs?status=success&per_page=1`);
    const run=(await r.json()).workflow_runs?.[0];
    if(run){ const d=new Date(run.updated_at);
      $('lastRun').textContent='ostatnie skuteczne odświeżenie: '+d.toLocaleString('pl-PL'); return; }
  }catch(e){}
  $('lastRun').textContent = 'ostatni pomiar w danych: '+(lastHistDate()||'—');
}

async function fire(light){
  if(!DATA.repo){ toast('Uzupełnij settings.github_repo w products.yaml i uruchom skrypt ponownie'); return; }
  if(!getToken()){ toast('Bez tokenu nie mogę uruchomić workflow'); return; }
  $('fireBtn').disabled=true; $('lightBtn').disabled=true;
  try{
    const r = await gh(`/repos/${DATA.repo}/actions/workflows/${WORKFLOW}/dispatches`,
      {method:'POST',body:JSON.stringify({ref:DATA.branch,
        inputs:{discovery: light?'skip':'full'}})});
    if(r.status!==204) throw new Error('HTTP '+r.status+(r.status===401?' (token?)':''));
    setStatus('run','Workflow uruchomiony…');
    toast(light?'💧 Light Fire — odświeżam ceny w znanych sklepach…':'🔥 Odpalone. Pełne discovery + ceny…');
    poll(Date.now());
  }catch(e){ $('fireBtn').disabled=false; $('lightBtn').disabled=false;
    setStatus('err','Błąd uruchomienia'); toast('Nie udało się: '+e.message); }
}
async function poll(since){
  try{
    const r = await gh(`/repos/${DATA.repo}/actions/runs?per_page=1&event=workflow_dispatch`);
    const run=(await r.json()).workflow_runs?.[0];
    if(run && new Date(run.created_at).getTime()>=since-60000){
      if(run.status==='completed'){
        if(run.conclusion==='success'){ setStatus('ok','Zakończono'); toast('Gotowe — odświeżam dane'); await refresh(true); }
        else { setStatus('err','Workflow: '+run.conclusion); toast('Workflow zakończony: '+run.conclusion); }
        $('fireBtn').disabled=false; $('lightBtn').disabled=false; return; }
      setStatus('run','W trakcie… ('+run.status+')');
    }
  }catch(e){}
  setTimeout(()=>poll(since),10000);
}

/* ================= RENDER ================= */
function render(){
  killCharts(); renderNav();
  const v=$('view');
  if(state.tab==='home') renderHome(v);
  else if(state.tab==='list') renderList(v);
  else if(state.tab==='cfg') renderConfig(v);
  else if(state.tab==='diag') renderDiag(v);
  else renderProduct(v, state.tab);
  $('genInfo').textContent=`wygenerowano ${DATA.generated}`+(DATA.repo?` · repo ${DATA.repo}`:'')
    +` · audyt ofert osadzony za ostatnie ${DATA.offers_days} dni (pełny po „Odśwież dane")`;
}
$('fireBtn').onclick=()=>fire(false);
$('lightBtn').onclick=()=>fire(true);
$('refreshBtn').onclick=()=>refresh(false);
$('tokenBtn').onclick=()=>{ getToken(true); toast('Token zapisany w tej przeglądarce'); };
setStatus('ok','Dane z pliku'); render(); loadLastRun();
</script>
</body>
</html>
"""


def _load_offers_for_embed():
    if not OFFERS_CSV.exists():
        return []
    since = (date.today() - timedelta(days=OFFERS_EMBED_DAYS)).isoformat()
    with OFFERS_CSV.open(newline="", encoding="utf-8") as f:
        return [r for r in csv.DictReader(f) if r.get("date", "") >= since]


def build_dashboard(rows, products, settings, generated):
    payload = {
        "generated": generated,
        "repo": (settings.get("github_repo") or "").strip(),
        "branch": (settings.get("branch") or "main").strip(),
        "offers_days": OFFERS_EMBED_DAYS,
        "products": [{"id": p["id"], "name": p.get("name", p["id"]),
                      "worldwide": bool(p.get("worldwide")),
                      "target_pln": p.get("target_pln")} for p in products],
        "history": rows,
        "offers": _load_offers_for_embed(),
        "serpapi": json.loads(QUOTA_FILE.read_text(encoding="utf-8"))
                   if QUOTA_FILE.exists() else None,
        "serper": json.loads(SERPER_QUOTA_FILE.read_text(encoding="utf-8"))
                  if SERPER_QUOTA_FILE.exists() else None,
        "runlog": (RUNLOG_FILE.read_text(encoding="utf-8")
                   .splitlines()[-RUNLOG_EMBED_LINES:]
                   if RUNLOG_FILE.exists() else []),
    }
    data_js = json.dumps(payload, ensure_ascii=False).replace("</", "<\\/")
    html = TEMPLATE.replace("__DATA__", data_js).replace("__WORKFLOW__", WORKFLOW_FILE)
    OUTPUT.mkdir(exist_ok=True)
    out = OUTPUT / "dashboard.html"
    out.write_text(html, encoding="utf-8")
    DOCS.mkdir(exist_ok=True)  # GitHub Pages: Settings -> Pages -> main /docs
    (DOCS / "index.html").write_text(html, encoding="utf-8")
    return out
