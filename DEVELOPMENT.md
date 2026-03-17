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
  │     └── fase/08-polish          ← refinamento + deploy
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

### FASE 8 — Polish & Deploy
**Branch**: `fase/08-polish`
**Entregáveis**:
- [ ] Dockerfile + docker-compose
- [ ] Testes end-to-end
- [ ] Error handling robusto
- [ ] Rate limiting inteligente
- [ ] Logging melhorado
- [ ] Documentação de deploy

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
