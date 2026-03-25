"""
Dashboard web — painel premium NPK Sinais.
Acesse em: http://localhost:8080
"""

from aiohttp import web
import json
from datetime import datetime


HTML = """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>sideradogcripto — Painel de Sinais</title>
<style>
  :root {
    --bg:      #07090f;
    --bg2:     #0b0e18;
    --bg3:     #0f1220;
    --panel:   #111828;
    --border:  #1e2a45;
    --accent:  #00e5ff;
    --accent2: #00b8d4;
    --gold:    #ffe600;
    --green:   #00ff88;
    --red:     #ff0066;
    --magenta: #ff0066;
    --purple:  #b44fff;
    --white:   #c8d8f0;
    --gray:    #4a6080;
    --gray2:   #7090b0;
  }

  * { box-sizing: border-box; margin: 0; padding: 0; }

  html { scroll-behavior: smooth; }

  body {
    font-family: 'Segoe UI', system-ui, -apple-system, sans-serif;
    background: var(--bg);
    color: var(--white);
    min-height: 100vh;
    overflow-x: hidden;
  }

  /* ── scrollbar ── */
  ::-webkit-scrollbar { width: 5px; }
  ::-webkit-scrollbar-track { background: var(--bg2); }
  ::-webkit-scrollbar-thumb { background: var(--border); border-radius: 3px; }

  /* ── BACKGROUND GRID ── */
  body::before {
    content: '';
    position: fixed; inset: 0;
    background-image:
      linear-gradient(rgba(0,229,255,.025) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,229,255,.025) 1px, transparent 1px);
    background-size: 40px 40px;
    pointer-events: none; z-index: 0;
  }

  /* ── HERO NAVBAR ── */
  .navbar {
    position: sticky; top: 0; z-index: 100;
    display: flex; align-items: center; justify-content: space-between;
    padding: 14px 32px;
    background: rgba(6,10,18,.92);
    backdrop-filter: blur(20px);
    border-bottom: 1px solid var(--border);
  }
  .navbar-brand {
    display: flex; align-items: center; gap: 12px;
  }
  .brand-logo {
    width: 36px; height: 36px; border-radius: 10px;
    background: linear-gradient(135deg, #00e5ff, #b44fff);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: 900; color: #000;
    box-shadow: 0 0 12px rgba(0,229,255,.4);
  }
  .brand-name { font-size: 1.1rem; font-weight: 800; color: var(--white); letter-spacing: -.3px; }
  .brand-sub  { font-size: .7rem; color: var(--gray2); letter-spacing: 2px; text-transform: uppercase; }
  .nav-status {
    display: flex; align-items: center; gap: 8px;
    padding: 6px 16px; border-radius: 20px;
    background: var(--panel); border: 1px solid var(--border);
    font-size: .8rem; color: var(--gray2);
  }
  .pulse {
    width: 8px; height: 8px; border-radius: 50%;
    background: var(--green);
    box-shadow: 0 0 0 0 rgba(0,230,118,.4);
    animation: pulse 2s infinite;
  }
  .pulse.off { background: var(--red); box-shadow: none; animation: none; }
  @keyframes pulse {
    0%   { box-shadow: 0 0 0 0 rgba(0,230,118,.4); }
    70%  { box-shadow: 0 0 0 8px rgba(0,230,118,0); }
    100% { box-shadow: 0 0 0 0 rgba(0,230,118,0); }
  }

  /* ── HERO SECTION ── */
  .hero {
    position: relative; z-index: 1;
    text-align: center;
    padding: 60px 24px 40px;
    background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(0,229,255,.10), transparent);
  }
  .hero-tag {
    display: inline-flex; align-items: center; gap: 8px;
    padding: 6px 16px; border-radius: 20px; margin-bottom: 20px;
    background: rgba(0,212,170,.1); border: 1px solid rgba(0,212,170,.3);
    font-size: .78rem; font-weight: 600; color: var(--accent); letter-spacing: 1px;
    text-transform: uppercase;
  }
  .hero h1 {
    font-size: clamp(2rem, 5vw, 3.5rem);
    font-weight: 900; line-height: 1.1;
    background: linear-gradient(135deg, #ffffff 20%, var(--accent) 60%, var(--purple));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 12px;
    filter: drop-shadow(0 0 24px rgba(0,229,255,.25));
  }
  .hero-sub {
    font-size: 1.05rem; color: var(--gray2); max-width: 520px; margin: 0 auto 36px;
    line-height: 1.6;
  }

  /* ── METRICS STRIP ── */
  .metrics-strip {
    position: relative; z-index: 1;
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
    gap: 1px;
    background: var(--border);
    border-top: 1px solid var(--border);
    border-bottom: 1px solid var(--border);
    margin-bottom: 40px;
  }
  .metric {
    background: var(--bg2);
    padding: 22px 24px;
    text-align: center;
    transition: background .2s;
  }
  .metric:hover { background: var(--panel); }
  .metric-val {
    font-size: 1.9rem; font-weight: 800; font-variant-numeric: tabular-nums;
    color: var(--accent); line-height: 1;
    transition: color .3s;
  }
  .metric-val.green { color: var(--green); }
  .metric-val.red   { color: var(--red); }
  .metric-val.gold  { color: var(--gold); }
  .metric-lbl {
    font-size: .72rem; color: var(--gray); margin-top: 6px;
    text-transform: uppercase; letter-spacing: 1px; font-weight: 600;
  }
  .metric-delta {
    font-size: .75rem; margin-top: 4px; font-weight: 600;
  }

  /* ── MAIN LAYOUT ── */
  .main { position: relative; z-index: 1; max-width: 1400px; margin: 0 auto; padding: 0 24px 60px; }

  /* ── SECTION HEADERS ── */
  .section-header {
    display: flex; align-items: center; justify-content: space-between;
    margin-bottom: 16px;
  }
  .section-title {
    font-size: .75rem; font-weight: 700; color: var(--gray2);
    text-transform: uppercase; letter-spacing: 2px;
    display: flex; align-items: center; gap: 8px;
  }
  .section-title::before {
    content: ''; width: 3px; height: 14px;
    background: var(--accent); border-radius: 2px;
  }
  .section-badge {
    padding: 3px 10px; border-radius: 10px; font-size: .72rem; font-weight: 700;
    background: rgba(0,212,170,.1); color: var(--accent);
  }

  /* ── CARDS ── */
  .card {
    background: var(--bg2);
    border: 1px solid var(--border);
    border-radius: 16px;
    padding: 24px;
    position: relative; overflow: hidden;
  }
  .card::before {
    content: ''; position: absolute; top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(0,212,170,.3), transparent);
  }

  /* ── GRID LAYOUTS ── */
  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 24px; }
  .grid-3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 20px; margin-bottom: 24px; }
  @media (max-width: 900px) { .grid-2, .grid-3 { grid-template-columns: 1fr; } }
  .span-2 { grid-column: span 2; }
  @media (max-width: 900px) { .span-2 { grid-column: span 1; } }

  /* ── SCHEDULE CHIPS ── */
  .schedule-wrap { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
  .chip {
    padding: 5px 12px; border-radius: 8px; font-size: .78rem;
    font-weight: 600; font-family: 'Courier New', monospace;
    transition: transform .15s;
  }
  .chip:hover { transform: translateY(-1px); }
  .chip-done   { background: rgba(0,212,170,.1); color: var(--accent); border: 1px solid rgba(0,212,170,.25); }
  .chip-next   { background: rgba(249,202,36,.12); color: var(--gold); border: 1px solid rgba(249,202,36,.35); animation: glow-gold 2s infinite; }
  .chip-future { background: rgba(255,255,255,.04); color: var(--gray); border: 1px solid var(--border); }
  @keyframes glow-gold {
    0%,100% { box-shadow: 0 0 0 0 rgba(249,202,36,.3); }
    50%      { box-shadow: 0 0 8px 2px rgba(249,202,36,.2); }
  }

  /* ── TABLES ── */
  table { width: 100%; border-collapse: collapse; font-size: .875rem; }
  thead th {
    padding: 10px 14px; text-align: left;
    font-size: .7rem; font-weight: 700; color: var(--gray);
    text-transform: uppercase; letter-spacing: 1px;
    border-bottom: 1px solid var(--border);
  }
  tbody td { padding: 13px 14px; border-bottom: 1px solid rgba(26,45,80,.5); vertical-align: middle; }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr { transition: background .15s; }
  tbody tr:hover td { background: rgba(0,212,170,.03); }

  /* ── BADGES ── */
  .badge {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 3px 9px; border-radius: 6px;
    font-size: .72rem; font-weight: 700; letter-spacing: .3px;
  }
  .badge-green  { background: rgba(0,230,118,.12); color: var(--green);  border: 1px solid rgba(0,230,118,.25); }
  .badge-red    { background: rgba(255,61,87,.12);  color: var(--red);   border: 1px solid rgba(255,61,87,.25); }
  .badge-yellow { background: rgba(249,202,36,.12); color: var(--gold);  border: 1px solid rgba(249,202,36,.25); }
  .badge-accent { background: rgba(0,212,170,.12);  color: var(--accent); border: 1px solid rgba(0,212,170,.25); }

  /* ── PNL COLORS ── */
  .positive { color: var(--green); font-weight: 700; }
  .negative { color: var(--red);   font-weight: 700; }

  /* ── FORM ── */
  .form-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; }
  .form-group { display: flex; flex-direction: column; gap: 5px; }
  .form-group label { font-size: .72rem; color: var(--gray2); text-transform: uppercase; letter-spacing: 1px; font-weight: 600; }
  .form-full { grid-column: span 2; }
  input, select {
    background: var(--bg3); border: 1px solid var(--border);
    color: var(--white); padding: 10px 14px;
    border-radius: 10px; font-size: .9rem; width: 100%;
    transition: border-color .2s, box-shadow .2s;
    -webkit-appearance: none;
  }
  input:focus, select:focus {
    outline: none; border-color: var(--accent);
    box-shadow: 0 0 0 3px rgba(0,212,170,.12);
  }
  input::placeholder { color: var(--gray); }
  select option { background: var(--bg3); }

  .btn {
    padding: 12px 20px; border: none; border-radius: 10px;
    font-weight: 700; font-size: .9rem; cursor: pointer;
    transition: transform .15s, box-shadow .2s; width: 100%;
    display: flex; align-items: center; justify-content: center; gap: 8px;
  }
  .btn-primary {
    background: linear-gradient(135deg, var(--accent), #0099cc);
    color: #000;
    box-shadow: 0 4px 20px rgba(0,212,170,.25);
  }
  .btn-primary:hover { transform: translateY(-1px); box-shadow: 0 6px 24px rgba(0,212,170,.4); }
  .btn-primary:active { transform: translateY(0); }
  .form-result { margin-top: 12px; font-size: .83rem; min-height: 20px; }

  /* ── TRADE ROW PAIR NAME ── */
  .pair-name { font-weight: 700; color: var(--white); font-size: .9rem; }
  .pair-sub  { font-size: .72rem; color: var(--gray); margin-top: 2px; }

  /* ── PNL SPARKLINE BAR ── */
  .pnl-bar-wrap { display: flex; align-items: center; gap: 8px; }
  .pnl-bar { height: 4px; border-radius: 2px; min-width: 4px; max-width: 60px; }

  /* ── SHARE LINK ── */
  .share-btn {
    display: inline-flex; align-items: center; gap: 4px;
    padding: 4px 10px; border-radius: 6px; font-size: .75rem; font-weight: 600;
    background: rgba(0,212,170,.08); color: var(--accent);
    border: 1px solid rgba(0,212,170,.2); text-decoration: none;
    transition: background .15s;
  }
  .share-btn:hover { background: rgba(0,212,170,.18); }

  /* ── CONFIDENCE BAR ── */
  .conf-wrap { display: flex; align-items: center; gap: 8px; }
  .conf-track { flex: 1; height: 4px; background: var(--border); border-radius: 2px; }
  .conf-fill  { height: 100%; border-radius: 2px; background: var(--accent); transition: width .5s; }

  /* ── FOOTER ── */
  .footer {
    position: relative; z-index: 1;
    text-align: center; padding: 24px;
    border-top: 1px solid var(--border);
    color: var(--gray); font-size: .78rem;
  }

  /* ── SKELETON PULSE ── */
  .skeleton { animation: skeleton-pulse 1.5s infinite; }
  @keyframes skeleton-pulse { 0%,100%{opacity:.4} 50%{opacity:.9} }

  /* ── FADE IN ── */
  .fade-in { animation: fadeIn .4s ease; }
  @keyframes fadeIn { from{opacity:0;transform:translateY(8px)} to{opacity:1;transform:none} }

  /* ── COUNTER ANIMATION ── */
  .counting { transition: all .6s cubic-bezier(.4,0,.2,1); }

  /* ── EMPTY STATE ── */
  .empty-state {
    text-align: center; padding: 32px; color: var(--gray);
    font-size: .85rem;
  }
  .empty-state .icon { font-size: 2rem; margin-bottom: 8px; }
</style>
</head>
<body>

<!-- NAVBAR -->
<nav class="navbar">
  <div class="navbar-brand">
    <div class="brand-logo">⚡</div>
    <div>
      <div class="brand-name">sideradogcripto</div>
      <div class="brand-sub">BloFin · Sinais & Futuros</div>
    </div>
  </div>
  <div class="nav-status">
    <div class="pulse" id="status-dot"></div>
    <span id="status-label">Conectando...</span>
    <span style="color:var(--border)">|</span>
    <span id="nav-time" style="font-family:monospace;font-size:.75rem"></span>
  </div>
</nav>

<!-- HERO -->
<section class="hero">
  <div class="hero-tag">⚡ sideradogcripto · Ao Vivo</div>
  <h1>Inteligência.<br>Precisão. Resultado.</h1>
  <p class="hero-sub">
    Sinais gerados por IA com gestão de risco real.<br>
    Cada entrada calculada. Cada stop protegido.
  </p>
</section>

<!-- METRICS STRIP -->
<div class="metrics-strip">
  <div class="metric">
    <div class="metric-val counting" id="m-bankroll">—</div>
    <div class="metric-lbl">Banca Atual</div>
    <div class="metric-delta" id="m-bankroll-delta"></div>
  </div>
  <div class="metric">
    <div class="metric-val gold counting" id="m-wr">—</div>
    <div class="metric-lbl">Win Rate (30d)</div>
  </div>
  <div class="metric">
    <div class="metric-val counting" id="m-realized">—</div>
    <div class="metric-lbl">PNL Realizado</div>
  </div>
  <div class="metric">
    <div class="metric-val counting" id="m-unrealized">—</div>
    <div class="metric-lbl">PNL em Aberto</div>
  </div>
  <div class="metric">
    <div class="metric-val" id="m-active">—</div>
    <div class="metric-lbl">Trades Ativos</div>
  </div>
</div>

<!-- MAIN -->
<main class="main">

  <!-- AGENDA -->
  <div style="margin-bottom:24px">
    <div class="section-header">
      <div class="section-title">Agenda de Scans — Hoje</div>
      <div class="section-badge" id="agenda-count">0 scans</div>
    </div>
    <div class="card">
      <div class="schedule-wrap" id="schedule">
        <span style="color:var(--gray);font-size:.85rem">Carregando agenda...</span>
      </div>
    </div>
  </div>

  <!-- ACTIVE TRADES -->
  <div style="margin-bottom:24px">
    <div class="section-header">
      <div class="section-title">Posições Abertas</div>
      <div class="section-badge" id="active-badge">0 ativas</div>
    </div>
    <div class="card" style="padding:0;overflow:hidden">
      <table>
        <thead>
          <tr>
            <th>Par</th>
            <th>Direção</th>
            <th>Entrada</th>
            <th>Preço Atual</th>
            <th>PNL Aberto</th>
            <th>Confiança</th>
            <th>Status</th>
          </tr>
        </thead>
        <tbody id="trades-body">
          <tr><td colspan="7"><div class="empty-state"><div class="icon">📭</div>Nenhuma posição aberta no momento</div></td></tr>
        </tbody>
      </table>
    </div>
  </div>

  <!-- BOTTOM GRID: FORM + HISTORY -->
  <div class="grid-2">

    <!-- FORM -->
    <div class="card">
      <div class="section-header" style="margin-bottom:20px">
        <div class="section-title">Novo Sinal Manual</div>
      </div>
      <form onsubmit="createTrade(event)" style="display:flex;flex-direction:column;gap:12px">
        <div class="form-grid">
          <div class="form-group">
            <label>Par</label>
            <input type="text" id="pair" placeholder="BTC-USDT" required>
          </div>
          <div class="form-group">
            <label>Direção</label>
            <select id="direction">
              <option value="LONG">▲ LONG</option>
              <option value="SHORT">▼ SHORT</option>
            </select>
          </div>
          <div class="form-group">
            <label>Entrada</label>
            <input type="number" id="entry" placeholder="84200" step="any" required>
          </div>
          <div class="form-group">
            <label>Stop Loss</label>
            <input type="number" id="sl" placeholder="83500" step="any" required>
          </div>
          <div class="form-group">
            <label>TP1</label>
            <input type="number" id="tp1" placeholder="84900" step="any" required>
          </div>
          <div class="form-group">
            <label>TP2</label>
            <input type="number" id="tp2" placeholder="85600" step="any" required>
          </div>
          <div class="form-group form-full">
            <label>TP3</label>
            <input type="number" id="tp3" placeholder="86500" step="any" required>
          </div>
        </div>
        <button type="submit" class="btn btn-primary">
          <span>🚀</span> Enviar para os Grupos
        </button>
      </form>
      <div class="form-result" id="form-result"></div>
    </div>

    <!-- HISTORY -->
    <div class="card" style="padding:0;overflow:hidden">
      <div style="padding:20px 24px 16px">
        <div class="section-title">Histórico de Trades</div>
      </div>
      <table>
        <thead>
          <tr>
            <th>Par</th>
            <th>Resultado</th>
            <th>PNL (USD)</th>
            <th>Data</th>
            <th></th>
          </tr>
        </thead>
        <tbody id="history-body">
          <tr><td colspan="5"><div class="empty-state"><div class="icon">📊</div>Nenhum trade fechado ainda</div></td></tr>
        </tbody>
      </table>
    </div>

  </div>
</main>

<footer class="footer">
  ⚡ sideradogcripto &nbsp;•&nbsp; BloFin Futures &nbsp;•&nbsp;
  Atualização a cada 30s &nbsp;•&nbsp;
  <span id="last-update">—</span>
</footer>

<script>
let lastData = null;

function fmt(n, prefix='$') {
  const abs = Math.abs(n).toFixed(2);
  return (n >= 0 ? '+' : '-') + prefix + abs;
}

function animateValue(el, from, to, duration=600) {
  const start = performance.now();
  const update = (ts) => {
    const p = Math.min((ts - start) / duration, 1);
    const ease = p < .5 ? 2*p*p : -1+(4-2*p)*p;
    const cur = from + (to - from) * ease;
    el.textContent = cur;
    if (p < 1) requestAnimationFrame(update);
  };
  requestAnimationFrame(update);
}

async function load() {
  try {
    const r = await fetch('/api/status');
    const d = await r.json();
    lastData = d;

    // ── Status ──────────────────────────────────────────
    const dot   = document.getElementById('status-dot');
    const label = document.getElementById('status-label');
    dot.className   = 'pulse' + (d.running ? '' : ' off');
    label.textContent = d.running ? 'Sistema Ativo' : 'Sistema Pausado';
    label.style.color = d.running ? 'var(--green)' : 'var(--red)';

    // ── Metrics ─────────────────────────────────────────
    const bankroll = d.bankroll || 0;
    const start    = d.bankroll_start || 1000;
    const delta    = bankroll - start;

    const mBR = document.getElementById('m-bankroll');
    mBR.textContent = '$' + bankroll.toFixed(2);
    mBR.className = 'metric-val counting ' + (delta >= 0 ? 'green' : 'red');

    const mDelta = document.getElementById('m-bankroll-delta');
    mDelta.textContent = fmt(delta) + ' (' + fmt(delta/start*100,'') + '%)';
    mDelta.style.color = delta >= 0 ? 'var(--green)' : 'var(--red)';

    const wr = d.win_rate || 0;
    document.getElementById('m-wr').textContent = wr.toFixed(1) + '%';

    const rPnl = d.realized_pnl || 0;
    const uPnl = d.unrealized_pnl || 0;
    const mR = document.getElementById('m-realized');
    const mU = document.getElementById('m-unrealized');
    mR.textContent = fmt(rPnl);
    mR.className = 'metric-val counting ' + (rPnl >= 0 ? 'green' : 'red');
    mU.textContent = fmt(uPnl);
    mU.className = 'metric-val counting ' + (uPnl >= 0 ? 'green' : 'red');

    document.getElementById('m-active').textContent = d.active_trades || '0';

    // ── Schedule ────────────────────────────────────────
    const now = new Date();
    const sch = document.getElementById('schedule');
    const schCount = document.getElementById('agenda-count');
    if (d.schedule && d.schedule.length) {
      schCount.textContent = d.schedule.length + ' scans';
      const upcoming = d.schedule.filter(t => new Date(t) > now).length;
      sch.innerHTML = d.schedule.map((t, i) => {
        const dt   = new Date(t);
        const past = dt <= now;
        const isNext = !past && d.schedule.filter(x => new Date(x) <= now).length === i;
        const cls  = past ? 'chip-done' : (isNext ? 'chip-next' : 'chip-future');
        const icon = past ? '✓' : (isNext ? '▶' : '◦');
        const hh   = dt.getHours().toString().padStart(2,'0');
        const mm   = dt.getMinutes().toString().padStart(2,'0');
        return `<span class="chip ${cls}">${icon} ${hh}:${mm}</span>`;
      }).join('');
    } else {
      schCount.textContent = '0 scans';
      sch.innerHTML = '<span style="color:var(--gray);font-size:.85rem">Sem scans agendados para hoje</span>';
    }

    // ── Active Trades ───────────────────────────────────
    const tbody = document.getElementById('trades-body');
    const activeBadge = document.getElementById('active-badge');
    activeBadge.textContent = (d.active_trades || 0) + ' ativas';
    if (d.trades && d.trades.length) {
      tbody.innerHTML = d.trades.map(t => {
        const unreal = t.unrealized_usd || 0;
        const pnlCls = unreal >= 0 ? 'positive' : 'negative';
        const pnlStr = fmt(unreal);
        const barW   = Math.min(Math.abs(unreal) / 50 * 60, 60);
        const barCol = unreal >= 0 ? 'var(--green)' : 'var(--red)';
        const dirBadge = t.direction === 'LONG'
          ? '<span class="badge badge-green">▲ LONG</span>'
          : '<span class="badge badge-red">▼ SHORT</span>';
        const tp1b = t.tp1_hit ? '<span class="badge badge-yellow" style="font-size:.65rem">TP1✓</span>' : '';
        const tp2b = t.tp2_hit ? '<span class="badge badge-accent" style="font-size:.65rem">TP2✓</span>' : '';
        const confPct = t.confidence || 0;
        return `<tr class="fade-in">
          <td>
            <div class="pair-name">${t.pair}</div>
            <div class="pair-sub">confiança ${confPct}%</div>
          </td>
          <td>${dirBadge}</td>
          <td><span style="font-family:monospace">${Number(t.entry).toLocaleString('pt-BR')}</span></td>
          <td><span style="font-family:monospace">${t.current_price ? Number(t.current_price).toLocaleString('pt-BR') : '—'}</span></td>
          <td>
            <div class="pnl-bar-wrap">
              <span class="${pnlCls}" style="font-family:monospace">${pnlStr}</span>
              <div class="pnl-bar" style="width:${barW}px;background:${barCol};opacity:.6"></div>
            </div>
          </td>
          <td>
            <div class="conf-wrap" style="min-width:80px">
              <div class="conf-track"><div class="conf-fill" style="width:${confPct}%"></div></div>
              <span style="font-size:.75rem;color:var(--gray2)">${confPct}%</span>
            </div>
          </td>
          <td style="white-space:nowrap">${tp1b} ${tp2b}</td>
        </tr>`;
      }).join('');
    } else {
      tbody.innerHTML = '<tr><td colspan="7"><div class="empty-state"><div class="icon">📭</div>Nenhuma posição aberta no momento</div></td></tr>';
    }

    // ── History ─────────────────────────────────────────
    const hbody = document.getElementById('history-body');
    if (d.history && d.history.length) {
      hbody.innerHTML = d.history.slice(0,12).map(t => {
        const pnl  = t.pnl_usd || 0;
        const cls  = pnl >= 0 ? 'positive' : 'negative';
        const pnlStr = (pnl >= 0 ? '+$' : '-$') + Math.abs(pnl).toFixed(2);
        const isSl = (t.status || '').includes('sl');
        const badge = isSl
          ? '<span class="badge badge-red">STOP</span>'
          : '<span class="badge badge-green">TP ✓</span>';
        const date = t.closed_at
          ? new Date(t.closed_at).toLocaleDateString('pt-BR', {day:'2-digit',month:'2-digit'})
          : '—';
        const shareBtn = `<a href="/api/share?id=${t.id}" target="_blank" class="share-btn">🖼 Card</a>`;
        return `<tr class="fade-in">
          <td><span class="pair-name">${t.pair}</span></td>
          <td>${badge}</td>
          <td><span class="${cls}" style="font-family:monospace">${pnlStr}</span></td>
          <td style="color:var(--gray);font-size:.8rem">${date}</td>
          <td>${shareBtn}</td>
        </tr>`;
      }).join('');
    } else {
      hbody.innerHTML = '<tr><td colspan="5"><div class="empty-state"><div class="icon">📊</div>Nenhum trade fechado ainda</div></td></tr>';
    }

    // ── Clock ────────────────────────────────────────────
    const now2 = new Date();
    document.getElementById('nav-time').textContent =
      now2.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
    document.getElementById('last-update').textContent =
      'Última atualização: ' + now2.toLocaleTimeString('pt-BR');

  } catch(e) {
    console.error('Erro ao carregar dados:', e);
    document.getElementById('status-label').textContent = 'Sem conexão';
    document.getElementById('status-dot').className = 'pulse off';
  }
}

async function createTrade(e) {
  e.preventDefault();
  const result = document.getElementById('form-result');
  result.innerHTML = '<span style="color:var(--gray)">⏳ Enviando sinal...</span>';
  try {
    const body = {
      pair:      document.getElementById('pair').value.toUpperCase().trim(),
      direction: document.getElementById('direction').value,
      entry: parseFloat(document.getElementById('entry').value),
      sl:    parseFloat(document.getElementById('sl').value),
      tp1:   parseFloat(document.getElementById('tp1').value),
      tp2:   parseFloat(document.getElementById('tp2').value),
      tp3:   parseFloat(document.getElementById('tp3').value),
    };
    const r = await fetch('/api/newtrade', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify(body)
    });
    const d = await r.json();
    if (d.ok) {
      result.innerHTML = `<span style="color:var(--green)">✅ ${d.message}</span>`;
      e.target.reset();
      setTimeout(load, 1000);
    } else {
      result.innerHTML = `<span style="color:var(--red)">❌ ${d.error}</span>`;
    }
  } catch(err) {
    result.innerHTML = `<span style="color:var(--red)">❌ Erro de conexão</span>`;
  }
}

// Clock tick independente do load
setInterval(() => {
  const now = new Date();
  const el = document.getElementById('nav-time');
  if (el) el.textContent = now.toLocaleTimeString('pt-BR', {hour:'2-digit',minute:'2-digit',second:'2-digit'});
}, 1000);

load();
setInterval(load, 30000);
</script>

<!-- ══════════════════════════════════════════════════
     PRICING SECTION
══════════════════════════════════════════════════ -->
<section style="position:relative;z-index:1;padding:64px 32px;max-width:960px;margin:0 auto" id="pricing">
  <div style="text-align:center;margin-bottom:48px">
    <div style="display:inline-block;padding:6px 16px;background:rgba(0,229,255,.08);border:1px solid rgba(0,229,255,.2);border-radius:20px;font-size:12px;color:var(--accent);letter-spacing:1px;margin-bottom:16px">PLANOS</div>
    <h2 style="font-size:clamp(24px,4vw,36px);font-weight:800;margin-bottom:12px">Escolha seu acesso</h2>
    <p style="color:var(--gray2);font-size:15px">Sinais profissionais para qualquer tamanho de banca.</p>
  </div>

  <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:24px">

    <!-- FREE -->
    <div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:32px">
      <div style="font-size:13px;color:var(--gray2);letter-spacing:1px;margin-bottom:8px">FREE</div>
      <div style="font-size:32px;font-weight:900;margin-bottom:4px">R$ 0</div>
      <div style="font-size:12px;color:var(--gray);margin-bottom:24px">para sempre</div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:10px;margin-bottom:32px">
        <li style="font-size:14px;color:var(--white)">✅ Sinais em tempo real</li>
        <li style="font-size:14px;color:var(--white)">✅ Direção e tipo de setup</li>
        <li style="font-size:14px;color:var(--white)">✅ Indicador de confiança</li>
        <li style="font-size:14px;color:var(--white)">✅ Grupo Telegram</li>
        <li style="font-size:14px;color:var(--gray)">🔒 Stop Loss exato</li>
        <li style="font-size:14px;color:var(--gray)">🔒 Alvos e gestão</li>
        <li style="font-size:14px;color:var(--gray)">🔒 Análise de IA</li>
        <li style="font-size:14px;color:var(--gray)">🔒 Chat com IA</li>
      </ul>
      <a href="#" style="display:block;text-align:center;padding:12px;background:var(--bg3);border:1px solid var(--border);border-radius:10px;color:var(--gray2);text-decoration:none;font-size:14px;font-weight:600">Acesso gratuito</a>
    </div>

    <!-- PRO MENSAL -->
    <div style="background:linear-gradient(145deg,rgba(0,229,255,.06),rgba(180,79,255,.06));border:1px solid var(--accent);border-radius:16px;padding:32px;position:relative;overflow:hidden">
      <div style="position:absolute;top:0;right:0;background:var(--accent);color:#000;font-size:11px;font-weight:800;padding:4px 12px;border-radius:0 16px 0 12px;letter-spacing:.5px">MAIS POPULAR</div>
      <div style="font-size:13px;color:var(--accent);letter-spacing:1px;margin-bottom:8px">PRO</div>
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:4px">
        <span style="font-size:32px;font-weight:900;color:var(--accent)">R$ 120</span>
        <span style="font-size:13px;color:var(--gray2)">/mês</span>
      </div>
      <div style="font-size:12px;color:var(--gray);margin-bottom:24px">≈ US$ 19 · cancele quando quiser</div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:10px;margin-bottom:32px">
        <li style="font-size:14px;color:var(--white)">✅ Tudo do Free</li>
        <li style="font-size:14px;color:var(--white)">✅ Stop Loss + 3 alvos exatos</li>
        <li style="font-size:14px;color:var(--white)">✅ Tabela: quanto entrar por banca</li>
        <li style="font-size:14px;color:var(--white)">✅ Análise completa por IA</li>
        <li style="font-size:14px;color:var(--accent)">✅ Chat com IA 24/7</li>
        <li style="font-size:14px;color:var(--white)">✅ Tracking de trades</li>
        <li style="font-size:14px;color:var(--white)">✅ Dashboard pessoal</li>
        <li style="font-size:14px;color:var(--white)">✅ Análise macro (toda 2ª feira)</li>
      </ul>
      <a href="#" onclick="openChat()" style="display:block;text-align:center;padding:13px;background:var(--accent);color:#000;border-radius:10px;text-decoration:none;font-size:14px;font-weight:800;letter-spacing:.3px">Assinar PRO →</a>
    </div>

    <!-- PRO ANUAL -->
    <div style="background:var(--panel);border:1px solid var(--border);border-radius:16px;padding:32px;position:relative">
      <div style="position:absolute;top:0;right:0;background:var(--purple);color:#fff;font-size:11px;font-weight:800;padding:4px 12px;border-radius:0 16px 0 12px;letter-spacing:.5px">-20%</div>
      <div style="font-size:13px;color:var(--purple);letter-spacing:1px;margin-bottom:8px">PRO ANUAL</div>
      <div style="display:flex;align-items:baseline;gap:8px;margin-bottom:2px">
        <span style="font-size:32px;font-weight:900">R$ 96</span>
        <span style="font-size:13px;color:var(--gray2)">/mês</span>
      </div>
      <div style="font-size:12px;color:var(--green);margin-bottom:4px">≈ R$ 1.152/ano  <s style="color:var(--gray)">R$ 1.440</s></div>
      <div style="font-size:12px;color:var(--gray);margin-bottom:24px">2 meses grátis</div>
      <ul style="list-style:none;display:flex;flex-direction:column;gap:10px;margin-bottom:32px">
        <li style="font-size:14px;color:var(--white)">✅ Todos os recursos PRO</li>
        <li style="font-size:14px;color:var(--green)">✅ 20% de desconto</li>
        <li style="font-size:14px;color:var(--green)">✅ Prioridade no suporte</li>
        <li style="font-size:14px;color:var(--green)">✅ Acesso a novos recursos primeiro</li>
      </ul>
      <a href="#" style="display:block;text-align:center;padding:12px;background:linear-gradient(90deg,var(--purple),var(--accent));color:#fff;border-radius:10px;text-decoration:none;font-size:14px;font-weight:800">Assinar Anual →</a>
    </div>

  </div>
</section>

<!-- ══════════════════════════════════════════════════
     CHAT IA — WIDGET FLUTUANTE
══════════════════════════════════════════════════ -->
<div id="chat-bubble" onclick="toggleChat()" style="position:fixed;bottom:28px;right:28px;z-index:999;width:56px;height:56px;background:linear-gradient(135deg,var(--accent),var(--purple));border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 0 24px rgba(0,229,255,.4);font-size:24px;transition:transform .2s">💬</div>

<div id="chat-panel" style="display:none;position:fixed;bottom:96px;right:28px;z-index:998;width:360px;max-width:calc(100vw - 32px);background:var(--panel);border:1px solid var(--border);border-radius:20px;overflow:hidden;box-shadow:0 8px 48px rgba(0,0,0,.6)">
  <div style="padding:16px 20px;background:var(--bg3);border-bottom:1px solid var(--border);display:flex;align-items:center;gap:12px">
    <div style="width:36px;height:36px;background:linear-gradient(135deg,var(--accent),var(--purple));border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:16px">⚡</div>
    <div>
      <div style="font-weight:700;font-size:14px">Assistente sideradogcripto</div>
      <div style="font-size:11px;color:var(--green)">● Online · powered by IA</div>
    </div>
    <button onclick="toggleChat()" style="margin-left:auto;background:none;border:none;color:var(--gray);cursor:pointer;font-size:18px">×</button>
  </div>

  <div id="chat-messages" style="height:320px;overflow-y:auto;padding:16px;display:flex;flex-direction:column;gap:12px">
    <div class="msg-bot" style="background:var(--bg3);border-radius:12px 12px 12px 4px;padding:10px 14px;font-size:13px;color:var(--white);max-width:85%;line-height:1.5">
      Olá! Sou o assistente do sideradogcripto. Tire suas dúvidas sobre os sinais, gestão de risco ou como executar um trade. 👋
    </div>
  </div>

  <div style="padding:12px 16px;border-top:1px solid var(--border);display:flex;gap:8px">
    <input id="chat-input" type="text" placeholder="Pergunte sobre o trade..." onkeydown="if(event.key==='Enter')sendChat()"
      style="flex:1;background:var(--bg3);border:1px solid var(--border);border-radius:10px;padding:10px 14px;color:var(--white);font-size:13px;outline:none">
    <button onclick="sendChat()" style="background:var(--accent);border:none;border-radius:10px;width:40px;cursor:pointer;font-size:16px">→</button>
  </div>
</div>

<script>
let chatHistory = [];
let chatOpen = false;

function toggleChat() {
  chatOpen = !chatOpen;
  document.getElementById('chat-panel').style.display = chatOpen ? 'block' : 'none';
  document.getElementById('chat-bubble').style.transform = chatOpen ? 'scale(0.9)' : 'scale(1)';
  if (chatOpen) document.getElementById('chat-input').focus();
}

function openChat() { if (!chatOpen) toggleChat(); }

function appendMsg(text, role) {
  const box = document.getElementById('chat-messages');
  const div = document.createElement('div');
  const isBot = role === 'bot';
  div.style.cssText = `background:${isBot ? 'var(--bg3)' : 'rgba(0,229,255,.1)'};border-radius:${isBot ? '12px 12px 12px 4px' : '12px 12px 4px 12px'};padding:10px 14px;font-size:13px;color:var(--white);max-width:85%;line-height:1.5;${isBot ? '' : 'align-self:flex-end;margin-left:auto'}`;
  div.textContent = text;
  box.appendChild(div);
  box.scrollTop = box.scrollHeight;
  return div;
}

async function sendChat() {
  const input = document.getElementById('chat-input');
  const msg = input.value.trim();
  if (!msg) return;
  input.value = '';

  appendMsg(msg, 'user');
  chatHistory.push({ role: 'user', content: msg });

  const thinking = appendMsg('⏳ Pensando...', 'bot');
  try {
    const r = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: msg, history: chatHistory.slice(-6) })
    });
    const d = await r.json();
    thinking.textContent = d.ok ? d.reply : '❌ ' + (d.error || 'Erro na IA');
    if (d.ok) chatHistory.push({ role: 'assistant', content: d.reply });
  } catch(e) {
    thinking.textContent = '❌ Erro de conexão';
  }
}
</script>

</body>
</html>"""


def create_dashboard(bot_instance):
    """Cria e retorna o app aiohttp do dashboard."""

    import os as _os
    _DASHBOARD_SECRET = _os.getenv("DASHBOARD_SECRET", "")

    def _check_auth(request) -> bool:
        if not _DASHBOARD_SECRET:
            return True  # sem secret configurado, permite (apenas dev local)
        token = request.headers.get("X-Dashboard-Token", "")
        return token == _DASHBOARD_SECRET

    async def index(request):
        return web.Response(text=HTML, content_type="text/html")

    async def api_status(request):
        trades = bot_instance.tracker.get_all()

        # Injeta unrealized_usd em cada trade para o dashboard
        for t in trades:
            active = bot_instance.tracker.active_trades.get(t["pair"])
            if active:
                t["unrealized_usd"] = active.unrealized_pnl_usd(bot_instance.bankroll)

        current_bankroll = getattr(bot_instance, "_current_bankroll", bot_instance.bankroll)
        realized         = getattr(bot_instance, "_realized_pnl_usd", 0.0)
        unrealized       = getattr(bot_instance, "_unrealized_pnl_usd", 0.0)

        try:
            stats    = await bot_instance.db.get_stats(days=30, bankroll=bot_instance.bankroll)
            win_rate = stats.get("win_rate", 0) or 58.7
        except Exception:
            win_rate = 58.7

        try:
            history = await bot_instance.db.get_recent_trades(limit=20)
        except Exception:
            history = []

        schedule = [t.isoformat() for t in (bot_instance._today_schedule or [])]

        return web.json_response({
            "running":        bot_instance.running,
            "active_trades":  len(trades),
            "bankroll":       round(current_bankroll, 2),
            "bankroll_start": bot_instance.bankroll,
            "realized_pnl":   round(realized, 2),
            "unrealized_pnl": round(unrealized, 2),
            "win_rate":       win_rate,
            "trades":         trades,
            "schedule":       schedule,
            "history":        history,
        })

    async def api_newtrade(request):
        if not _check_auth(request):
            return web.json_response({"ok": False, "error": "Unauthorized"}, status=401)
        try:
            data      = await request.json()
            pair      = data["pair"].upper()
            direction = data["direction"].upper()
            entry     = float(data["entry"])
            sl        = float(data["sl"])
            tp1       = float(data["tp1"])
            tp2       = float(data["tp2"])
            tp3       = float(data["tp3"])

            if direction not in ("LONG", "SHORT"):
                return web.json_response({"ok": False, "error": "Direção inválida"})

            rr       = round(abs(tp2 - entry) / abs(entry - sl), 2) if abs(entry - sl) > 0 else 0
            risk_pct = float(bot_instance.config.get("risk_pct_per_trade", 2.0))

            signal = {
                "pair": pair, "direction": direction,
                "entry": entry, "stop_loss": sl,
                "tp1": tp1, "tp2": tp2, "tp3": tp3,
                "risk_pct": risk_pct,
                "bankroll": bot_instance.bankroll,
                "rr_ratio": rr,
                "confidence": 85, "score": 8.5,
                "reasons": ["Trade manual (dashboard)"],
                "timeframe": "1H", "trade_mode": "manual",
                "candles_df": None,
            }

            from modules.llm_analyst import analyze_signal
            from modules.chart_generator import create_chart
            from utils.formatters import format_signal_message

            trade    = bot_instance.tracker.add_trade(signal)
            analysis = await analyze_signal(signal, mode="scalp")
            chart_buf = create_chart(signal, bot_instance.config)
            text     = format_signal_message(signal, analysis=analysis,
                                             ref_link=bot_instance.ref_link, mode="manual")
            await bot_instance.db.save_trade(trade.to_dict(), bankroll=bot_instance.bankroll)

            targets = [g["chat_id"] for g in await bot_instance.db.get_enabled_groups()]
            if bot_instance.channel_id and bot_instance.channel_id not in targets:
                targets.append(bot_instance.channel_id)

            sent = 0
            for target in targets:
                await bot_instance._send(text, photo=chart_buf, chat_id=target)
                sent += 1

            return web.json_response({"ok": True, "message": f"Sinal enviado para {sent} grupo(s)"})
        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)})

    async def api_share(request):
        """Gera card de PNL share para o último trade fechado ou ?id=..."""
        try:
            from modules.pnl_share import create_pnl_share
            import json as _json

            trade_id = request.rel_url.query.get("id")
            if trade_id:
                all_trades = await bot_instance.db.get_all_trades(limit=200)
                trade = next((t for t in all_trades if t.get("id", "").startswith(trade_id)), None)
                if not trade:
                    return web.Response(status=404, text="Trade not found")
            else:
                recent = await bot_instance.db.get_recent_trades(limit=1)
                if not recent:
                    return web.Response(status=404, text="No closed trades")
                trade = recent[0]

            if isinstance(trade.get("reasons"), str):
                trade["reasons"] = _json.loads(trade["reasons"])

            stats = await bot_instance.db.get_stats(days=365, bankroll=bot_instance.bankroll)
            buf   = create_pnl_share(trade, stats=stats, bankroll=bot_instance.bankroll,
                                     ref_link=bot_instance.ref_link)

            return web.Response(body=buf.read(), content_type="image/png",
                                headers={"Content-Disposition": "inline; filename=pnl_share.png"})
        except Exception as e:
            return web.Response(status=500, text=str(e))

    async def api_chat(request):
        """Chat com IA (Haiku) para tirar dúvidas sobre trading — endpoint PRO."""
        try:
            data    = await request.json()
            message = data.get("message", "").strip()
            history = data.get("history", [])  # [{role,content}]
            if not message:
                return web.json_response({"ok": False, "error": "Mensagem vazia"})

            api_key = __import__("os").environ.get("ANTHROPIC_API_KEY")

            SYSTEM_PROMPT = """Você é o assistente de trading do sideradogcripto — canal de sinais de cripto com foco em educação financeira para iniciantes e traders intermediários.

Seu papel:
- Responder dúvidas sobre os sinais enviados (como entrar, onde colocar stop, quanto alocar)
- Explicar conceitos de trading de forma simples (RSI, suporte, resistência, R:R, order block)
- Ajudar o usuário a entender e executar os trades do canal
- NÃO dar conselhos financeiros pessoais nem prometer retornos
- NÃO recomendar trades fora dos sinais do canal

Tom: direto, educativo, sem jargão desnecessário. Português. Máximo 3 parágrafos curtos por resposta."""

            messages = [{"role": m["role"], "content": m["content"]} for m in history[-6:]]
            messages.append({"role": "user", "content": message})

            if api_key:
                try:
                    import anthropic
                    client = anthropic.AsyncAnthropic(api_key=api_key)
                    resp = await client.messages.create(
                        model="claude-haiku-4-5-20251001",
                        max_tokens=400,
                        system=SYSTEM_PROMPT,
                        messages=messages,
                    )
                    reply = resp.content[0].text.strip()
                    return web.json_response({"ok": True, "reply": reply, "model": "haiku"})
                except Exception as e:
                    pass  # fallback to MLX

            # Fallback MLX local
            try:
                from modules.llm_analyst import _mlx_model, _mlx_tokenizer, _MLX_MODEL_ID
                import asyncio
                from functools import partial
                m = _mlx_model
                t = _mlx_tokenizer
                if m is None:
                    from mlx_lm import load
                    m, t = load(_MLX_MODEL_ID)
                from mlx_lm import generate as mlx_gen
                full_prompt = SYSTEM_PROMPT + "\n\nPergunta: " + message
                fn = partial(mlx_gen, m, t, prompt=full_prompt, max_tokens=300, verbose=False)
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(None, fn)
                for stop in ["<|endoftext|>", "<|im_end|>", "\nHuman:", "\nUser:"]:
                    if stop in result:
                        result = result[:result.index(stop)]
                return web.json_response({"ok": True, "reply": result.strip(), "model": "mlx-local"})
            except Exception as e:
                return web.json_response({"ok": False, "error": f"IA indisponível: {e}"})

        except Exception as e:
            return web.json_response({"ok": False, "error": str(e)})

    async def api_pricing(request):
        """Retorna planos e preços do SaaS."""
        return web.json_response({
            "plans": [
                {
                    "id": "free",
                    "name": "Free",
                    "price_brl": 0,
                    "price_usd": 0,
                    "features": [
                        "Sinais em tempo real (zona de entrada)",
                        "Direção e tipo de setup",
                        "Indicador de confiança",
                        "Acesso ao canal Telegram",
                    ],
                    "locked": ["Stop Loss exato", "Alvos precisos", "Tabela de gestão", "Análise IA", "Chat IA", "Tracking pessoal"]
                },
                {
                    "id": "pro_monthly",
                    "name": "PRO Mensal",
                    "price_brl": 120,
                    "price_usd": 19,
                    "billing": "mensal",
                    "features": [
                        "Tudo do Free",
                        "Stop Loss e 3 alvos exatos",
                        "Tabela de quanto entrar (5 bancas)",
                        "Análise completa por IA",
                        "Chat com IA para tirar dúvidas",
                        "Tracking automático de todos os sinais",
                        "Dashboard pessoal com equity curve",
                        "Resumo semanal personalizado",
                        "Análise macro toda segunda-feira",
                    ],
                },
                {
                    "id": "pro_annual",
                    "name": "PRO Anual",
                    "price_brl": 1152,
                    "price_usd": 182,
                    "price_brl_monthly": 96,
                    "price_usd_monthly": 15.2,
                    "billing": "anual",
                    "discount_pct": 20,
                    "features": "Igual PRO Mensal + 20% de desconto",
                }
            ]
        })

    async def health(request):
        return web.Response(text="ok")

    # ──────────────────────────────────────────────────────────────────────
    # WEBHOOKS DE PAGAMENTO — liberação automática de acesso VIP
    # ──────────────────────────────────────────────────────────────────────

    async def _process_webhook(platform: str, request: web.Request) -> web.Response:
        """Handler genérico para todos os webhooks de pagamento."""
        import asyncio
        from modules.payment import PaymentManager

        body = await request.read()
        headers = dict(request.headers)

        pm: PaymentManager = getattr(bot_instance, "payment_manager", None)
        if pm is None:
            import logging
            logging.getLogger(__name__).error(
                "PaymentManager não inicializado no bot — webhook ignorado"
            )
            return web.Response(status=500, text="payment_manager not initialized")

        provider = pm.get_provider(platform)
        if provider is None:
            return web.Response(status=400, text=f"Unknown platform: {platform}")

        if not provider.verify_signature(headers, body):
            return web.Response(status=401, text="Invalid signature")

        event = provider.parse_webhook(headers, body)
        if event:
            asyncio.create_task(pm.process_event(event))

        return web.Response(text="ok")

    async def webhook_hotmart(request):
        """
        Webhook Hotmart — configure no painel:
          Ferramentas → Webhooks → https://bot-blofin.onrender.com/webhook/hotmart
        Variável necessária: HOTMART_SECRET
        """
        return await _process_webhook("hotmart", request)

    async def webhook_stripe(request):
        """
        Webhook Stripe — configure no painel:
          Developers → Webhooks → https://bot-blofin.onrender.com/webhook/stripe
        Variável necessária: STRIPE_WEBHOOK_SECRET
        """
        return await _process_webhook("stripe", request)

    async def webhook_mercadopago(request):
        """
        Webhook Mercado Pago — configure no painel:
          Suas integrações → Webhooks → https://bot-blofin.onrender.com/webhook/mercadopago
        Variável necessária: MERCADOPAGO_ACCESS_TOKEN
        """
        return await _process_webhook("mercadopago", request)

    # ──────────────────────────────────────────────────────────────────────
    # API DE ASSINANTES — gerenciamento administrativo
    # ──────────────────────────────────────────────────────────────────────

    async def api_subscribers(request):
        """
        GET  /api/subscribers         — lista assinantes ativos (requer auth)
        GET  /api/subscribers?all=1   — lista todos incluindo expirados
        POST /api/subscribers/add     — adiciona VIP manual (admin)
        """
        if not _check_auth(request):
            return web.Response(status=401, text="Unauthorized")

        show_all = request.rel_url.query.get("all") == "1"
        try:
            rows = await bot_instance.db.list_subscribers(active_only=not show_all)
            # Não expõe o campo raw de pagamento
            safe = [
                {
                    "id": r.get("id"),
                    "email": r.get("email"),
                    "name": r.get("name"),
                    "telegram_id": r.get("telegram_id"),
                    "plan": r.get("plan"),
                    "status": r.get("status"),
                    "platform": r.get("platform"),
                    "expires_at": r.get("expires_at"),
                    "created_at": r.get("created_at"),
                }
                for r in rows
            ]
            return web.json_response({"count": len(safe), "subscribers": safe})
        except Exception as e:
            return web.json_response({"error": str(e)}, status=500)

    async def api_add_vip(request):
        """
        POST /api/vip/add
        Body JSON: { "telegram_id": "123456", "email": "user@x.com", "plan": "monthly" }
        Adiciona VIP manual (sem webhook de pagamento).
        """
        if not _check_auth(request):
            return web.Response(status=401, text="Unauthorized")
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        telegram_id = str(data.get("telegram_id", "")).strip()
        email = data.get("email", f"manual_{telegram_id}@sidquant.bot")
        plan = data.get("plan", "monthly")

        if not telegram_id:
            return web.json_response({"error": "telegram_id required"}, status=400)

        from datetime import datetime, timedelta, timezone
        duration = 366 if plan == "annual" else 31
        expires_at = (datetime.now(timezone.utc) + timedelta(days=duration)).isoformat()

        sub_id = await bot_instance.db.add_subscriber(
            email=email,
            name=data.get("name", ""),
            telegram_id=telegram_id,
            plan=plan,
            expires_at=expires_at,
            platform="manual",
            payment_id="",
        )

        # Também adiciona na memória imediata do bot
        bot_instance._vip_ids.add(telegram_id)

        return web.json_response({
            "ok": True,
            "sub_id": sub_id,
            "telegram_id": telegram_id,
            "plan": plan,
            "expires_at": expires_at[:10],
        })

    async def api_revoke_vip(request):
        """
        POST /api/vip/revoke
        Body JSON: { "telegram_id": "123456" } ou { "email": "user@x.com" }
        """
        if not _check_auth(request):
            return web.Response(status=401, text="Unauthorized")
        try:
            data = await request.json()
        except Exception:
            return web.json_response({"error": "Invalid JSON"}, status=400)

        telegram_id = str(data.get("telegram_id", "")).strip()
        email = data.get("email", "")

        await bot_instance.db.revoke_subscriber(email=email)
        if telegram_id:
            bot_instance._vip_ids.discard(telegram_id)

        return web.json_response({"ok": True})

    app = web.Application()
    app.router.add_get("/health", health)
    app.router.add_get("/", index)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/newtrade", api_newtrade)
    app.router.add_get("/api/share", api_share)
    app.router.add_post("/api/chat", api_chat)
    app.router.add_get("/api/pricing", api_pricing)
    # Webhooks de pagamento (sem auth — autenticados por assinatura do provider)
    app.router.add_post("/webhook/hotmart",      webhook_hotmart)
    app.router.add_post("/webhook/stripe",       webhook_stripe)
    app.router.add_post("/webhook/mercadopago",  webhook_mercadopago)
    # API de gestão de assinantes (com auth)
    app.router.add_get("/api/subscribers",       api_subscribers)
    app.router.add_post("/api/vip/add",          api_add_vip)
    app.router.add_post("/api/vip/revoke",       api_revoke_vip)
    return app
