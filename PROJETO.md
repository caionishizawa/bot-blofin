# SIDQUANT BOT — BRIEFING COMPLETO PARA NOVO CHAT
# Versão: 2.0 | Última atualização: 27/03/2026

---

## VISÃO DO PRODUTO

Bot de sinais de cripto para o canal do **sideradog** (@sideradogcripto).
Gera sinais técnicos automáticos, analisa com Claude Haiku e distribui
exclusivamente para o grupo **Sid Quantt** no tópico **BOT IA** (thread_id=150).

Monetização dupla:
- **Referral BloFin**: cada usuário que abre conta via link gera comissão de taxa
- **VIP (a lançar)**: acesso a análises premium + dashboard

---

## ESTADO ATUAL (27/03/2026)

### Infraestrutura — PRODUÇÃO ✅
- **Deploy**: https://bot-blofin.onrender.com (Render free tier — sem sleep via self-ping)
- **Banco**: PostgreSQL externo no Render (`dpg-d714okruibrs739no690-a.oregon-postgres.render.com`)
- **GitHub**: https://github.com/caionishizawa/bot-blofin (branch `main`)
- **Health check**: `/health` → retorna `ok`
- **Dashboard**: `/` (protegido por `DASHBOARD_SECRET`)
- **Self-ping**: bot pinga `/health` a cada 10min para evitar sleep do free tier

### Bot Telegram — FUNCIONANDO ✅
- **Bot**: @SidQuantBot
- **Grupo**: Sid Quantt (`-1003848794457`)
- **Tópico**: BOT IA (`thread_id=150`) — TODAS as mensagens vão aqui
- **Admin ID**: `1655218530` (@siderapg)
- **Referral**: https://partner.blofin.com/d/sideradog

### Pipeline de Sinais — FUNCIONANDO ✅
```
BloFin API → Scanner (12 indicadores) → Confluência (min 3) →
_register_trade() → salva PostgreSQL →
Claude Haiku (análise PT-BR) → Chart TradingView dark →
→ _send() → free_channel_id + thread_id=150 (BOT IA)
```

### Proteções Anti-Duplicação ✅
- `_portfolio_sent_date` — portfolio executa 1x/dia no máximo
- `_morning_sent_date` — bom dia enviado 1x/dia às 08:00 BRT
- Restart após 09h → não re-agenda portfolio do dia
- Midnight reset — flags limpos à meia-noite para novo dia

---

## VARIÁVEIS DE AMBIENTE (PRODUÇÃO — RENDER)

```env
TELEGRAM_BOT_TOKEN=8298817575:AAH6BmNi14q-Fm88n0c-3C1EQE4OnbKFD-E
TELEGRAM_FREE_CHANNEL_ID=-1003848794457
TELEGRAM_CHANNEL_ID=-1003848794457
TELEGRAM_THREAD_ID=150
TELEGRAM_ADMIN_ID=1655218530
ADMIN_IDS=1655218530
TELEGRAM_REF_LINK=https://partner.blofin.com/d/sideradog
ANTHROPIC_API_KEY=sk-ant-api03-...
DATABASE_URL=postgresql://sidquant_user:...@dpg-d714okruibrs739no690-a.oregon-postgres.render.com/sidquant
DASHBOARD_SECRET=sideradog2026!blofin
CALCULATOR_LINK=          ← preencher quando tiver a URL da calculadora
LOG_LEVEL=INFO
# RENDER_EXTERNAL_URL é injetado automaticamente pelo Render
```

---

## ARQUITETURA DE ARQUIVOS

```
bot-blofin/
├── src/
│   ├── bot.py              ← orquestrador principal
│   │   ├── _send()         ← SEMPRE envia para free_channel_id + thread_id
│   │   ├── _reply()        ← reply_text com message_thread_id automático
│   │   ├── _register_trade()      ← tracker + DB em um só lugar
│   │   ├── _persist_trade_event() ← salva evento TP/SL no DB
│   │   ├── _check_gap_events()    ← detecta SL/TP durante downtime
│   │   └── _health_check_loop()   ← self-ping 10min + alerta 25h
│   ├── dashboard.py        ← painel web (aiohttp) + botão Opus
│   ├── modules/
│   │   ├── scanner.py          ← 12 indicadores + confluência
│   │   ├── chart_generator.py  ← charts TradingView dark
│   │   ├── llm_analyst.py      ← Claude Haiku + Opus sob demanda
│   │   ├── tracker.py          ← ActiveTrade + restore_from_db_row()
│   │   ├── performance.py      ← PostgreSQL/SQLite + métricas PNL
│   │   └── pnl_share.py        ← card visual de resultado
│   └── utils/
│       ├── blofin_api.py   ← REST client + rate limiting
│       └── formatters.py   ← templates de mensagem Telegram
```

---

## CICLO DE VIDA DE UM TRADE (modular)

```
1. NOVO SINAL
   └── _register_trade(signal)
         ├── tracker.add_trade()   → memória
         └── db.save_trade()       → PostgreSQL ✅ IMEDIATO

2. MONITORAMENTO (loop 60s)
   └── _update_trades()
         ├── api.get_all_mark_prices()  → batch
         └── trade.check_levels(price)
               └── se evento → _persist_trade_event()
                     ├── db.save_trade()  → atualiza status/pnl ✅
                     └── _send() → notifica BOT IA

3. RESTART / DEPLOY
   └── startup:
         ├── db.get_open_trades()         → busca abertos no PostgreSQL
         ├── tracker.restore_from_db_row() → restaura tp_hit flags
         └── _check_gap_events()           → candles 1m últimos 30min
               └── se SL/TP bateu → _persist_trade_event() ✅
```

---

## AGENDA DE SINAIS (horários BRT)

- **08:00** — Mensagem bom dia + preço BTC em tempo real
- **09:00** — Portfolio scan (4H, 6 pares com hedge direcional)
- **09:30 → 21:30** — 6 sinais disparados em horários aleatórios ao longo do dia
- **Domingo 20:00** — Resumo semanal de performance

---

## API ENDPOINTS (Dashboard)

| Endpoint | Método | Auth | Descrição |
|---|---|---|---|
| `/health` | GET | ❌ | Health check (usado pelo self-ping) |
| `/` | GET | ✅ | Dashboard principal |
| `/api/status` | GET | ✅ | Trades ativos, métricas |
| `/api/opus-signal` | POST | ✅ | Análise completa com Claude Opus |
| `/api/subscribers` | GET | ✅ | Lista VIPs ativos |
| `/webhook/hotmart` | POST | 🔑 | Webhook Hotmart |
| `/webhook/stripe` | POST | 🔑 | Webhook Stripe |
| `/webhook/mercadopago` | POST | 🔑 | Webhook Mercado Pago |

---

## COMANDOS TELEGRAM

| Comando | Acesso | Descrição |
|---|---|---|
| `/scan` | Admin | Escanear pares agora |
| `/trades` | Admin | Ver trades ativos |
| `/stats` | Admin | Performance semanal/mensal/anual |
| `/newtrade PAR DIR ENTRY SL TP1 TP2 TP3` | Admin | Trade manual |
| `/cleartrades` | Admin | Limpar tracker |
| `/agenda` | Admin | Ver agenda de scans do dia |
| `/broadcast TEXTO` | Admin | Enviar mensagem para BOT IA |
| `/macro` | Admin | Análise macro semanal manual |
| `/ask PERGUNTA` | Todos | Agente educacional (3/dia FREE) |
| `/mentor` | VIP | Modo conversa livre |

---

## FASES CONCLUÍDAS

| Fase | Descrição | Status |
|---|---|---|
| 1 | BloFin API wrapper (REST + WebSocket) | ✅ |
| 2 | Scanner (12 indicadores + confluência) | ✅ |
| 3 | Chart Generator (TradingView dark theme) | ✅ |
| 4 | LLM Analyst (Claude Haiku + Opus on-demand) | ✅ |
| 5 | Trade Tracker (monitoramento SL/TP real-time) | ✅ |
| 6 | Telegram Bot (comandos + envio tópico BOT IA) | ✅ |
| 7 | Performance DB (PNL, win rate, equity curve) | ✅ |
| 8 | Deploy produção (Render, PostgreSQL, health check) | ✅ |
| 9 | Agente Educacional (/ask, /mentor, knowledge base) | ✅ |
| 10 | Trade persistence + gap check pós-restart | ✅ |
| 11 | Self-ping anti-sleep Render free tier | ✅ |
| 12 | Arquitetura modular (_register_trade, _persist_event) | ✅ |

---

## PRÓXIMAS FASES

### Fase 13 — Monetização (PRÓXIMA PRIORIDADE)
- [ ] Criar canal FREE público separado no Telegram
- [ ] Landing page: hero + resultados do bot + CTA assinar VIP
- [ ] Configurar Hotmart ou Stripe para cobrança automática
- [ ] Webhook → libera VIP automaticamente após pagamento
- [ ] URL da calculadora de posição → `CALCULATOR_LINK` no Render

### Fase 14 — Horários BRT corretos
- [ ] Portfolio scan às 09:00 BRT (12:00 UTC) — hoje dispara às 06:00 BRT
- [ ] Slots de envio 09:30–21:30 BRT (hoje são UTC = 06:30–18:30 BRT)
- [ ] Usar `pytz` para garantir timezone correto no Render

### Fase 15 — Dashboard público para assinantes
- [ ] Login do assinante (Telegram ID ou email)
- [ ] Histórico de sinais pessoal
- [ ] Performance do bot em tempo real (win rate, PNL acumulado)
- [ ] Link de afiliado do BloFin personalizado

### Fase 16 — Multi-influenciador
- [ ] Config por canal (cada influenciador tem seu grupo e ref link)
- [ ] Arquitetura suporta — só falta UI de onboarding

---

## BUGS CORRIGIDOS (histórico completo)

| Bug | Arquivo | Fix | Data |
|---|---|---|---|
| Qualquer usuário era admin | bot.py | Bloqueia se ADMIN_IDS vazia | 24/03 |
| TP3 em gap → PNL errado | tracker.py | TP1/TP2 marcados no TP3 | 24/03 |
| Trade breakeven = derrota | performance.py | `< 0` ao invés de `<= 0` | 24/03 |
| Porta hardcoded (não subia no Render) | bot.py | Lê PORT env var | 24/03 |
| Portfolio disparava múltiplas vezes | bot.py | Flag _portfolio_sent_date | 25/03 |
| Header do portfolio sendo enviado | bot.py | Removido — só sinais | 25/03 |
| Sinais duplicados pós-restart | bot.py | Bloqueia scan se restart após 09h | 25/03 |
| Mensagens indo para General (wrong topic) | bot.py | _reply() com message_thread_id | 26/03 |
| _send() com multi-target confuso | bot.py | Sempre usa free_channel_id + thread_id | 27/03 |
| Trades perdidos no restart | tracker.py | restore_from_db_row() | 27/03 |
| SL/TP não detectado durante downtime | bot.py | _check_gap_events() | 27/03 |
| Bot dormindo após 15min (Render free) | bot.py | Self-ping a cada 10min | 27/03 |
| add_trade + save_trade espalhados | bot.py | _register_trade() centralizado | 27/03 |

---

## PARA PRÓXIMO CHAT

1. **Deploy pendente**: subir as mudanças de 27/03 para o Render via push
2. **Calculator link**: quando tiver a URL, adicionar `CALCULATOR_LINK` nas env vars do Render
3. **Horários BRT**: portfolio scan dispara cedo demais (06:00 BRT) — corrigir na Fase 14
4. **UptimeRobot**: configurar em uptimerobot.com como backup do self-ping (gratuito, 5min)
5. **Fase 13**: monetização é o próximo passo mais importante para gerar receita
