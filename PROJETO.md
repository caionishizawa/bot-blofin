# SIDQUANT BOT — BRIEFING COMPLETO PARA NOVO CHAT
# Versão: 1.0 | Data: 24/03/2026

---

## VISÃO DO PRODUTO

Bot de sinais de cripto para o canal do **sideradog** (@sideradogcripto).
Gera sinais técnicos automáticos, analisa com Claude Haiku e distribui para
grupos Telegram segmentados (FREE = teaser / VIP = sinal completo).

Monetização dupla:
- **Referral BloFin**: cada usuário que abre conta via link gera comissão de taxa
- **VIP $39/mês**: acesso ao sinal completo antes de acontecer + dashboard

---

## ESTADO ATUAL (24/03/2026)

### Infraestrutura — PRODUÇÃO ✅
- **Deploy**: https://bot-blofin.onrender.com (Render Starter $7/mês)
- **Banco**: PostgreSQL no Render (externo: `dpg-d714okruibrs739no690-a.oregon-postgres.render.com`)
- **GitHub**: https://github.com/caionishizawa/bot-blofin (branch `main`)
- **Health check**: `/health` → retorna `ok`
- **Dashboard API**: `/api/status`, `/api/newtrade` (auth: `X-Dashboard-Token`)

### Bot Telegram — FUNCIONANDO ✅
- **Bot**: @SidQuantBot (token: `8298817575:AAH6BmNi14q...`)
- **Canal FREE**: SidQuant Free (`-1003753035878`) — teaser pós-fato com CTA
- **Canal VIP**: Sid Quantt (`-1003848794457`) — sinal completo antes de acontecer
- **Admin ID**: `1655218530` (@siderapg)
- **Referral**: https://partner.blofin.com/d/sideradog

### Pipeline de Sinais — FUNCIONANDO ✅
```
BloFin API → Scanner (12 indicadores) → Confluência (min 3) →
Claude Haiku (análise PT-BR) → Chart TradingView dark →
→ VIP: sinal completo + chart + análise
→ FREE: resultado pós-fato quando trade fecha
```

### LLM — Claude Haiku ✅
- Modelo: `claude-haiku-4-5-20251001`
- API Key: `sk-ant-api03-cVlWXYbWFAzjnZE9r...` (Anthropic Console)
- Custo estimado: ~$0.15/mês (5 sinais/dia)
- Fallback: MLX local → Ollama → análise por código

---

## ARQUITETURA DE ARQUIVOS

```
bot-blofin/
├── Dockerfile                  ← build de produção
├── docker-compose.yml          ← dev local com PostgreSQL
├── railway.toml                ← config Railway (alternativa)
├── render.yaml                 ← config Render (produção)
├── .env                        ← variáveis locais (não commitado)
├── .env.example                ← template documentado
├── requirements.txt            ← deps Python
├── config.yaml                 ← pares, timeframes, filtros
├── DEVELOPMENT.md              ← roadmap de fases (1-9)
├── PROJETO.md                  ← este arquivo
└── src/
    ├── bot.py                  ← orquestrador principal
    ├── dashboard.py            ← painel web (aiohttp)
    ├── modules/
    │   ├── scanner.py          ← 12 indicadores + confluência
    │   ├── chart_generator.py  ← charts TradingView dark
    │   ├── llm_analyst.py      ← Claude Haiku + fallbacks
    │   ├── tracker.py          ← monitoramento SL/TP em tempo real
    │   ├── performance.py      ← PostgreSQL/SQLite + métricas PNL
    │   └── pnl_share.py        ← card visual de resultado
    └── utils/
        ├── blofin_api.py       ← REST client + rate limiting + retry
        └── formatters.py       ← templates de mensagem Telegram
```

---

## VARIÁVEIS DE AMBIENTE (PRODUÇÃO)

```env
TELEGRAM_BOT_TOKEN=8298817575:AAH6BmNi14q-Fm88n0c-3C1EQE4OnbKFD-E
TELEGRAM_VIP_CHANNEL_ID=-1003848794457
TELEGRAM_FREE_CHANNEL_ID=-1003753035878
TELEGRAM_CHANNEL_ID=-1003848794457
TELEGRAM_ADMIN_ID=1655218530
ADMIN_IDS=1655218530
TELEGRAM_REF_LINK=https://partner.blofin.com/d/sideradog
ANTHROPIC_API_KEY=sk-ant-api03-cVlWXYbWFAzjnZE9rlX3f5APDt2H8LagxoiSQX739xKh-u65Bid_L_JCCOhYdcpxeOf6cKh3hMh_mfUZ3dkQ9w-oR4wsQA
DATABASE_URL=postgresql://sidquant_user:JRy3NT1OOrnPTIuIpYRTDtOA5YOWiEG1@dpg-d714okruibrs739no690-a.oregon-postgres.render.com/sidquant
DASHBOARD_SECRET=sideradog2026!blofin
LOG_LEVEL=INFO
```

---

## INDICADORES TÉCNICOS (scanner.py)

1. EMA 9/21 Cross
2. EMA Trend (preço vs EMA50)
3. RSI (14) — zonas oversold/overbought
4. MACD Cross (12/26/9)
5. MACD Histogram momentum
6. Bollinger Bands (20, 2σ)
7. ATR (14) — volatilidade para SL/TP
8. ADX (14) — força da tendência
9. Volume confirmation
10. Suporte/Resistência por pivot points
11. Order Block detection
12. RSI Divergência

**Confluência mínima**: 3 de 12 para emitir sinal
**Filtros de qualidade**: `min_confidence: 72` | `min_rr: 1.5` | `max_rr: 6.0`

---

## SIZING DO TRADE

```
Risk por trade: 1% da banca
TP1: fecha 50% da posição
TP2: fecha 30% da posição
TP3: fecha 20% da posição (fecha trade)
SL:  fecha posição restante
```

---

## PARES MONITORADOS (config.yaml)

BTC-USDT, ETH-USDT, SOL-USDT, XRP-USDT, DOGE-USDT,
ADA-USDT, AVAX-USDT, LINK-USDT, DOT-USDT, MATIC-USDT

---

## AGENDA DE SINAIS

Bot agenda 6 missões/dia automaticamente baseado no dia da semana:
- Timeframes: 15m (scalp) | 1H (intraday) | 4H (swing)
- Swing days (seg/qua/sex): inclui análise 4H macro semanal
- Relatório semanal automático (domingo)

---

## API ENDPOINTS (Dashboard)

| Endpoint | Método | Auth | Descrição |
|---|---|---|---|
| `/health` | GET | ❌ | Health check |
| `/api/status` | GET | ❌ | Trades ativos, métricas |
| `/api/newtrade` | POST | ✅ | Criar sinal manual |
| `/api/share` | GET | ❌ | Card PNL do último trade |
| `/api/pricing` | GET | ❌ | Planos e preços |
| `/api/chat` | POST | ❌ | Análise LLM de sinal |

**Auth**: Header `X-Dashboard-Token: sideradog2026!blofin`

### Exemplo — criar sinal manual:
```bash
curl -X POST https://bot-blofin.onrender.com/api/newtrade \
  -H "Content-Type: application/json" \
  -H "X-Dashboard-Token: sideradog2026!blofin" \
  -d '{
    "pair": "BTC-USDT",
    "direction": "LONG",
    "entry": 87500,
    "sl": 85800,
    "tp1": 89200,
    "tp2": 90800,
    "tp3": 93000
  }'
```

---

## MODELO DE NEGÓCIO

```
Funil:
  Conteúdo sideradog (resultados pós-fato no FREE)
    ↓ FOMO "quero pegar antes"
  Landing page (a construir)
    ↓ CTA Assinar VIP $39/mês
  Checkout (PIX / Crypto / Cartão)
    ↓ Pagamento confirmado
  Admin libera acesso VIP manualmente (MVP)
    ↓ Acesso ao grupo Sid Quantt + Dashboard

Receita adicional (passiva):
  Cada assinante opera na BloFin → taxa de trading
  → comissão automática para sideradog
```

**Preço VIP**: $39/mês
**Breakeven infra**: 1 assinante (R$7 Render)

---

## FASES CONCLUÍDAS

- ✅ Fase 1: BloFin API wrapper (REST + WebSocket)
- ✅ Fase 2: Scanner (12 indicadores + confluência)
- ✅ Fase 3: Chart Generator (TradingView dark theme)
- ✅ Fase 4: LLM Analyst (Claude Haiku + fallbacks)
- ✅ Fase 5: Trade Tracker (monitoramento SL/TP real-time)
- ✅ Fase 6: Telegram Bot (7+ comandos, FREE/VIP channels)
- ✅ Fase 7: Performance DB (PNL, win rate, equity curve)
- ✅ Fase 8: Deploy produção (Docker, PostgreSQL, Render, health check)

---

## PRÓXIMAS FASES

### Fase 9 — Agente Educacional com Memória (PLANEJADO)
Bot responde dúvidas de trading baseado no conhecimento do sideradog.

```
/ask Como valido uma entrada com confluência?
/mentor → modo conversa livre (VIP only)
```

Arquitetura:
- `src/agent/knowledge_base.md` — sideradog documenta seus setups
- `src/agent/memory.py` — histórico por usuário (nível, dúvidas)
- FREE: 3 perguntas/dia (Haiku) | VIP: ilimitado (Sonnet)

**Pré-requisito**: sideradog escrever o `knowledge_base.md` com:
- Setups favoritos e por quê
- Regras de gestão de risco pessoais
- Checklist de validação de entrada
- Erros comuns de iniciante

### Fase 10 — SaaS Completo (FUTURO)
- Landing page de vendas
- Checkout automático (Stripe + PIX + Crypto)
- Auto-liberação VIP via webhook de pagamento
- Multi-influenciador (cada um com canal e ref próprio)
- Dashboard do assinante (login, histórico, performance)

---

## COMANDOS ÚTEIS

```bash
# Deploy local (dev)
cd bot-blofin
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env  # preencher tokens
python src/bot.py

# Enviar sinal manual de teste
curl -X POST https://bot-blofin.onrender.com/api/newtrade \
  -H "X-Dashboard-Token: sideradog2026!blofin" \
  -H "Content-Type: application/json" \
  -d '{"pair":"ETH-USDT","direction":"LONG","entry":2050,"sl":2000,"tp1":2100,"tp2":2150,"tp3":2250}'

# Ver trades ativos
curl https://bot-blofin.onrender.com/api/status

# Push para produção
git add -A && git commit -m "feat: descrição" && git push origin main
# Render redeploya automaticamente após o push
```

---

## BUGS CORRIGIDOS NESTA SESSÃO

| Bug | Arquivo | Fix |
|---|---|---|
| Qualquer usuário era admin | `bot.py` | Bloqueia se `ADMIN_IDS` vazia |
| `/api/newtrade` sem auth | `dashboard.py` | Header `X-Dashboard-Token` |
| TP3 em gap → PNL errado | `tracker.py` | TP1/TP2 marcados no TP3 |
| Trade breakeven = derrota | `performance.py` | `< 0` ao invés de `<= 0` |
| Porta hardcoded (não subia no Render) | `bot.py` | Lê `PORT` env var |
| DATABASE_URL interno não resolvia | `performance.py` | SSL + fallback SQLite |
| Modelo Opus (caro) | `llm_analyst.py` | Trocado para Haiku |

---

## NOTAS PARA PRÓXIMO CHAT

1. **Sinal já sendo gerado**: bot está em produção, sinais chegando no VIP automaticamente
2. **Próxima entrega prioritária**: landing page de vendas + checkout para monetizar
3. **Fase 9 (agente)**: só começa após sideradog escrever o `knowledge_base.md`
4. **BloFin API keys**: ainda não configuradas (só endpoints públicos ativos)
5. **Canal FREE**: ainda igual ao VIP — criar canal público separado e trocar o ID
6. **Multi-influenciador**: arquitetura suporta, implementar na Fase 10
