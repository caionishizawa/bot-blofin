# 🔄 Git Workflow & Fases de Desenvolvimento

## Estratégia de Branches

```
main          ← produção estável, só merges testados
  │
  ├── develop        ← branch de integração (testes gerais)
  │     │
  │     ├── fase/01-foundation      ← estrutura + BloFin API
  │     ├── fase/02-scanner         ← indicadores + sinais
  │     ├── fase/03-charts          ← geração de gráficos
  │     ├── fase/04-llm             ← análise com IA
  │     ├── fase/05-tracker         ← monitoramento real-time
  │     ├── fase/06-telegram        ← bot + comandos
  │     ├── fase/07-performance     ← PNL + relatórios
  │     ├── fase/08-polish          ← refinamento + deploy
  │     └── fase/09-agente          ← agente educacional com memória
  │
  └── hotfix/*       ← correções urgentes em produção
```

## Tags de Versão (para rollback fácil)

```
v0.1.0  — Foundation (API wrapper + config)
v0.2.0  — Scanner funcionando
v0.3.0  — Charts gerados
v0.4.0  — LLM integrado
v0.5.0  — Tracker ativo
v0.6.0  — Telegram bot rodando
v0.7.0  — Performance DB completo
v0.8.0  — Beta (tudo integrado)
v0.9.0  — Agente educacional ativo
v1.0.0  — Produção
```

### Rollback rápido:
```bash
# Ver todas as versões
git tag -l

# Voltar para versão específica
git checkout v0.3.0

# Criar branch de correção a partir de versão antiga
git checkout -b hotfix/fix-chart v0.3.0
```

---

## Fases Detalhadas

### FASE 1 — Foundation ✅
**Branch**: `fase/01-foundation`
**Entregáveis**:
- [x] Estrutura de pastas
- [x] config.example.yaml
- [x] requirements.txt
- [x] .gitignore
- [x] BloFin API wrapper (REST + WebSocket)
- [x] README.md

**Teste**: `python -c "from src.utils.blofin_api import BloFinAPI; print('OK')"`

---

### FASE 2 — Scanner + Indicadores ✅
**Branch**: `fase/02-scanner`
**Entregáveis**:
- [x] indicators.py (12 indicadores técnicos)
- [x] scanner.py (scan de pares, detecção de sinais)
- [x] Lógica de confluência (mín. 3 confluências)

**Teste**: 
```bash
python tests/test_scanner.py
# Deve: puxar candles BTC-USDT, calcular indicadores, retornar signal ou None
```

---

### FASE 3 — Chart Generator ✅
**Branch**: `fase/03-charts`
**Entregáveis**:
- [x] chart_generator.py
- [x] Tema TradingView dark
- [x] Marcação de Entry/SL/TP com zonas coloridas
- [x] Subplots: Volume, RSI, MACD
- [x] Watermark do canal

**Teste**: 
```bash
python tests/test_charts.py
# Deve: gerar PNG de chart com todos os elementos visuais
```

---

### FASE 4 — LLM Analyst ✅
**Branch**: `fase/04-llm`
**Entregáveis**:
- [x] llm_analyst.py
- [x] Prompt profissional em PT-BR
- [x] Fallback sem LLM
- [x] Análise horária simplificada

**Teste**: 
```bash
python tests/test_llm.py
# Deve: gerar texto de análise a partir de dados mock
```

---

### FASE 5 — Trade Tracker ✅
**Branch**: `fase/05-tracker`
**Entregáveis**:
- [x] tracker.py
- [x] ActiveTrade com check_levels()
- [x] Modo polling (REST) e WebSocket
- [x] Callbacks para eventos (SL/TP)
- [x] Update horário

**Teste**: 
```bash
python tests/test_tracker.py
# Deve: simular trades e detectar SL/TP corretamente
```

---

### FASE 6 — Telegram Bot ✅
**Branch**: `fase/06-telegram`
**Entregáveis**:
- [x] bot.py (orquestrador)
- [x] formatters.py (templates de mensagem)
- [x] Comandos: /start, /stats, /pnl, /trades, /scan, /stop, /resume
- [x] Scheduler de 5 sinais/dia
- [x] Ref link em toda mensagem

**Teste**: 
```bash
python tests/test_bot.py
# Deve: responder /start e /stats em DM de teste
```

---

### FASE 7 — Performance DB ✅
**Branch**: `fase/07-performance`
**Entregáveis**:
- [x] performance.py (SQLite)
- [x] Win rate, PNL, drawdown, profit factor, streak
- [x] Relatório semanal automático
- [x] Gráfico de equity curve

**Teste**: 
```bash
python tests/test_performance.py
# Deve: salvar trades mock, calcular stats, gerar PNL chart
```

---

### FASE 8 — Polish & Deploy ✅
**Branch**: `fase/08-polish`
**Entregáveis**:
- [x] Dockerfile + docker-compose
- [x] Deploy no Render com PostgreSQL externo
- [x] Error handling robusto (try/except em todos os módulos críticos)
- [x] Rate limiting + retry na BloFin API
- [x] Logging estruturado (LOG_LEVEL env var)
- [x] Health check `/health` — alerta admin se >25h sem sinal
- [x] Fallback SQLite quando PostgreSQL indisponível
- [x] Correção de bugs críticos (admin check, TP3 gap, breakeven, porta hardcoded)
- [x] Dashboard web com painel de sinais e pricing

---

### FASE 10 — SaaS Completo (Checkout + Monetização)
**Branch**: `fase/10-saas`
**Status**: 🏗️ INFRAESTRUTURA PRONTA — aguardando configuração da plataforma de checkout

**O que foi implementado:**
- [x] Módulo de pagamento modular (`src/modules/payment/`)
  - [x] `base.py` — interface abstrata para todos os providers
  - [x] `hotmart.py` — webhook Hotmart com verificação de assinatura
  - [x] `stripe_handler.py` — webhook Stripe com verificação HMAC-SHA256
  - [x] `mercadopago_handler.py` — webhook Mercado Pago
  - [x] `manager.py` — orquestrador: processa evento → libera VIP → notifica no Telegram
- [x] Tabela `subscribers` no banco (PostgreSQL + SQLite)
  - Campos: id, email, name, telegram_id, plan, status, platform, payment_id, expires_at
- [x] Métodos DB: `add_subscriber`, `is_vip_subscriber`, `get_subscriber`, `list_subscribers`, `revoke_subscriber`, `expire_stale_subscribers`
- [x] Endpoints de webhook no dashboard:
  - `POST /webhook/hotmart`
  - `POST /webhook/stripe`
  - `POST /webhook/mercadopago`
- [x] Endpoints de gestão de assinantes:
  - `GET /api/subscribers` — lista VIPs ativos (admin)
  - `POST /api/vip/add` — adiciona VIP manual via API
  - `POST /api/vip/revoke` — revoga VIP via API
- [x] `_is_vip_async()` no bot — checa banco em tempo real (não só env var)
- [x] Comando `/minhaconta` — usuário consulta status e validade da assinatura

**O que falta configurar (não código — só variáveis de ambiente):**

| Plataforma | Variável | Onde pegar |
|---|---|---|
| Hotmart | `HOTMART_SECRET` | Ferramentas → Webhooks → Segurança |
| Stripe | `STRIPE_WEBHOOK_SECRET` | Developers → Webhooks → Signing secret |
| Mercado Pago | `MERCADOPAGO_ACCESS_TOKEN` | Suas integrações → Credenciais |

**Como ativar Hotmart (passo a passo):**
```
1. Criar produto no Hotmart (R$ 120/mês ou R$ 1.152/ano)
2. No checkout, adicionar campo personalizado: "Seu usuário no Telegram"
3. Em Ferramentas → Webhooks → Adicionar:
   URL: https://bot-blofin.onrender.com/webhook/hotmart
   Eventos: PURCHASE_COMPLETE, PURCHASE_REFUNDED, SUBSCRIPTION_CANCELLATION
4. Copiar o token de segurança → HOTMART_SECRET no Render
5. Testar com compra de teste
```

**Entregáveis pendentes para completar a Fase 10:**
- [ ] Landing page de vendas (hero + prova social + CTA)
- [ ] Canal FREE público separado no Telegram
- [ ] Configurar plataforma de checkout escolhida
- [ ] Testar fluxo completo: compra → webhook → VIP automático

---

### FASE 9 — Agente Educacional com Memória
**Branch**: `fase/09-agente`
**Status**: 🔮 PLANEJADO — implementar após Fase 8 e primeiros pagantes

**Visão:**
Um agente conversacional no Telegram (mesmo bot) que responde dúvidas
de trading com base no conhecimento acumulado do sideradog.
Não substitui os sinais — complementa como professor/mentor 24h.

**Casos de uso principais:**
- "Como validar um sinal antes de entrar?"
- "O que é confluência? Quantas preciso?"
- "Qual o tamanho de posição ideal para iniciante?"
- "Esse setup que postaram é confiável?"
- "Explica o que é RSI / MACD / Bollinger"
- "Errei o stop, o que aprendo disso?"

**Arquitetura planejada:**

```
[Usuário manda pergunta no DM do bot]
         │
         ▼
[Agente Claude Sonnet/Haiku]
    ├── Contexto 1: Base de conhecimento do sideradog
    │     └── Arquivo(s) MD com tudo que ele já ensinou:
    │           - setups favoritos dele
    │           - regras de gestão de risco
    │           - como ele valida entradas
    │           - erros comuns de iniciante
    │           - filosofia de trade dele
    │
    ├── Contexto 2: Memória do usuário (por Telegram ID)
    │     └── SQLite/PostgreSQL: histórico de perguntas,
    │           nível percebido (iniciante/intermediário),
    │           dúvidas recorrentes, última interação
    │
    ├── Contexto 3: Sinais recentes do bot
    │     └── Injeta os últimos 3-5 sinais como contexto
    │           para o agente referenciar exemplos reais
    │
    └── Resposta personalizada em PT-BR
          + disclaimer obrigatório ao final
          + sugestão de próximo passo (ex: "veja o sinal de hoje")
```

**Base de conhecimento (knowledge base):**
- Arquivo: `src/agent/knowledge_base.md`
- Populado manualmente pelo sideradog ao longo do tempo
- Estruturado por tópicos: setups, gestão, psicologia, iniciantes
- Claude usa como RAG simplificado (inject no system prompt)
- Evolui conforme o produto cresce

**Memória por usuário:**
- Tabela `agent_memory` no PostgreSQL
- Campos: `telegram_id`, `level`, `last_topics[]`, `summary`, `updated_at`
- A cada conversa, atualiza o summary com o que o usuário já aprendeu
- Personaliza respostas: iniciante recebe mais contexto, avançado vai direto

**Acesso:**
- FREE: 3 perguntas/dia ao agente
- VIP: ilimitado + respostas mais detalhadas (Sonnet ao invés de Haiku)

**Comando Telegram:**
```
/ask Como valido uma entrada com confluência?
/ask O que você acha desse setup: RSI 28 + preço no suporte?
/mentor  → abre modo conversa livre (VIP only)
```

**Entregáveis da Fase 9:**
- [ ] `src/agent/agent.py` — orquestrador do agente
- [ ] `src/agent/knowledge_base.md` — base inicial populada pelo sideradog
- [ ] `src/agent/memory.py` — leitura/escrita de memória por usuário
- [ ] Integração com bot.py (comando /ask e /mentor)
- [ ] Tabela `agent_memory` no schema PostgreSQL
- [ ] Lógica de limite (3/dia FREE, ilimitado VIP)
- [ ] Disclaimer automático em toda resposta

**Teste**:
```bash
python tests/test_agent.py
# Deve: responder pergunta usando knowledge base,
#        lembrar contexto da conversa anterior,
#        aplicar limite correto por tier
```

**Notas para quando chegar nessa fase:**
- Pedir para o sideradog gravar um documento com tudo que ele ensina:
  setups, regras de gestão, erros comuns, como ele analisa o mercado
- Esse documento vira a personalidade e conhecimento do agente
- Quanto mais rico o knowledge_base.md, melhor o agente
- Considerar fine-tuning futuro quando tiver 1000+ perguntas reais

---

## Comandos Git do Dia a Dia

```bash
# Começar trabalho numa fase
git checkout develop
git pull
git checkout -b fase/02-scanner

# Trabalhar, commitar
git add .
git commit -m "feat(scanner): add RSI + MACD indicators"

# Finalizar fase
git checkout develop
git merge fase/02-scanner
git tag -a v0.2.0 -m "Scanner + indicadores funcionando"
git push origin develop --tags

# Promover para produção
git checkout main
git merge develop
git push origin main

# ROLLBACK em caso de problema
git checkout main
git revert HEAD                   # desfaz último commit
# ou
git reset --hard v0.5.0           # volta para versão específica
git push origin main --force      # ⚠️ cuidado com force push
```

## Conventional Commits

Use este padrão nos commits para histórico limpo:

```
feat(módulo): descrição        → nova feature
fix(módulo): descrição         → correção de bug
refactor(módulo): descrição    → refatoração sem mudança de behavior
test(módulo): descrição        → testes
docs: descrição                → documentação
chore: descrição               → manutenção (deps, config)
```

Exemplos:
```
feat(scanner): add Bollinger Bands + volume confirmation
fix(tracker): websocket reconnect on timeout
refactor(chart): extract color palette to constants
test(performance): add PNL calculation edge cases
docs: update README with deploy instructions
chore: bump anthropic SDK to 0.35.0
```
