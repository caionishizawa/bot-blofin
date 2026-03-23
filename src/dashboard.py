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
<title>NPK Sinais — Painel de Resultados</title>
<style>
  :root {
    --bg:      #060a12;
    --bg2:     #0b1120;
    --bg3:     #0f1829;
    --panel:   #111d35;
    --border:  #1a2d50;
    --accent:  #00d4aa;
    --accent2: #00b894;
    --gold:    #f9ca24;
    --green:   #00e676;
    --red:     #ff3d57;
    --white:   #e8f0fe;
    --gray:    #5a6a8a;
    --gray2:   #8899bb;
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
      linear-gradient(rgba(0,212,170,.03) 1px, transparent 1px),
      linear-gradient(90deg, rgba(0,212,170,.03) 1px, transparent 1px);
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
    background: linear-gradient(135deg, var(--accent), #0077ff);
    display: flex; align-items: center; justify-content: center;
    font-size: 18px; font-weight: 900; color: #000;
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
    background: radial-gradient(ellipse 80% 50% at 50% 0%, rgba(0,212,170,.12), transparent);
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
    background: linear-gradient(135deg, #fff 30%, var(--accent));
    -webkit-background-clip: text; -webkit-text-fill-color: transparent;
    background-clip: text; margin-bottom: 12px;
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
    <div class="brand-logo">N</div>
    <div>
      <div class="brand-name">NPK Sinais</div>
      <div class="brand-sub">BloFin Futures Intelligence</div>
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
  <div class="hero-tag">⚡ Resultados em Tempo Real</div>
  <h1>Sinais com<br>Precisão Cirúrgica</h1>
  <p class="hero-sub">
    Análise quantitativa com IA, gestão de risco profissional e
    rastreamento de PNL em tempo real para o mercado de futuros.
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
  NPK Sinais &nbsp;•&nbsp; BloFin Futures &nbsp;•&nbsp;
  Atualização automática a cada 30s &nbsp;•&nbsp;
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
</body>
</html>"""


def create_dashboard(bot_instance):
    """Cria e retorna o app aiohttp do dashboard."""

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
            win_rate = stats.get("win_rate", 0)
        except Exception:
            win_rate = 0

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

    app = web.Application()
    app.router.add_get("/", index)
    app.router.add_get("/api/status", api_status)
    app.router.add_post("/api/newtrade", api_newtrade)
    app.router.add_get("/api/share", api_share)
    return app
