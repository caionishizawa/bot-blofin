# BASE DE CONHECIMENTO — SIDERADOG CRIPTO
## Atualizada continuamente. Quanto mais rica, mais preciso o agente.

---

## 📌 QUEM É O SIDERADOG

Trader focado em cripto desde 2020. Especialista em leitura técnica, confluência de indicadores e gestão de risco para iniciantes e intermediários. Opera principalmente BTC, ETH, SOL e altcoins de alta liquidez. Filosofia: **consistência bate sorte**. Prefere setups de alta probabilidade com RR ≥ 2, mesmo que aconteçam menos vezes.

---

## 🎯 SETUPS FAVORITOS

### 1. EMA Cross + Volume (Setup Principal)
- **Condição**: EMA9 cruza acima da EMA21 com volume acima da média
- **Timeframe ideal**: 1H (intraday), 4H (swing)
- **Por quê funciona**: o cruzamento sinaliza mudança de momentum. Volume confirma que não é falso.
- **Entrada**: candle de confirmação FECHADO acima do cruzamento
- **Stop Loss**: abaixo da EMA21 (ou abaixo do candle de sinal)
- **Confluência extra**: RSI saindo de zona oversold (< 40) ao mesmo tempo

### 2. RSI Oversold + Suporte (Reversão)
- **Condição**: RSI abaixo de 32 + preço em suporte histórico
- **Timeframe ideal**: 4H ou 1D para sinais mais fortes
- **Por quê funciona**: acumulação de ordens de compra em suporte quando o ativo está "barato" tecnicamente
- **Entrada**: aguardar RSI cruzar de volta acima de 35 (confirma saída da zona)
- **Stop Loss**: abaixo do suporte (2-3% de margem)
- **CUIDADO**: Em tendência de baixa forte (ADX > 40 bearish), RSI oversold pode ser armadilha

### 3. MACD Cross + Histograma Crescendo
- **Condição**: MACD linha cruza acima da signal + histograma virando positivo
- **Timeframe ideal**: 1H a 4H
- **Regra do sideradog**: só entro se o histograma do MACD já virou para cima ≥ 2 candles. Histograma virando no primeiro candle pode ser falso.
- **Confirmação adicional**: preço acima da EMA50

### 4. Order Block Retest (Setup Avançado)
- **Condição**: preço retorna a uma zona de order block (zona de impulso anterior) com candle de rejeição
- **Timeframe ideal**: 4H e 1D
- **Como identificar o OB**: o candle imediatamente ANTES de um movimento forte = order block
- **Entrada**: quando o preço toca a zona e forma candle de rejeição (doji, martelo, engolfista)
- **Stop Loss**: abaixo do order block (invalida a zona)

### 5. Bollinger Squeeze + Rompimento
- **Condição**: bandas Bollinger muito apertadas (squeeze) → expansão com volume
- **Por quê funciona**: períodos de baixa volatilidade sempre precedem movimentos grandes
- **Entrada**: candle de rompimento da banda SUPERIOR (LONG) ou INFERIOR (SHORT) com volume
- **Não entre**: se o rompimento for sem volume — fakeout clássico

---

## 📊 INDICADORES — COMO EU USO CADA UM

### RSI (14)
- **< 30**: oversold — zona de compra potencial (mas espera confirmação)
- **> 70**: overbought — zona de venda/cautela
- **50**: linha de tendência. Acima = bullish. Abaixo = bearish.
- **Divergência de alta**: preço faz fundo mais baixo, RSI faz fundo mais alto → reversão à vista
- **Divergência de baixa**: preço faz topo mais alto, RSI faz topo mais baixo → exaustão

### MACD (12/26/9)
- **Cross bullish**: linha MACD cruza acima da signal → compra
- **Cross bearish**: linha MACD cruza abaixo → venda/saída
- **Histograma**: barras crescendo = momentum aumentando; barras diminuindo = momentum perdendo força
- **Dica**: o MACD é lento. Use-o para confirmar direção, não para timing exato de entrada

### Médias Móveis (EMA 9, 21, 50, 200)
- **EMA9 > EMA21 > EMA50**: tendência de alta bem definida. Verde para LONG.
- **EMA9 < EMA21 < EMA50**: tendência de baixa. Cuidado com LONGs.
- **Preço acima da EMA200**: mercado bull no longo prazo
- **Golden Cross (EMA50 cruza EMA200)**: sinal macro de alta. Não aparece todo mês.

### Bollinger Bands (20, 2σ)
- **Preço toca banda inferior**: suporte dinâmico — zona de compra em tendência de alta
- **Preço toca banda superior**: resistência dinâmica — zona de venda em tendência de baixa
- **Squeeze (bandas juntas)**: energia acumulando. Grande move vindo aí.

### ATR (14)
- **Uso principal**: dimensionar o Stop Loss. SL = entrada - (ATR × 1.5) para LONG
- **ATR alto**: volatilidade alta → posição menor para controlar risco
- **ATR baixo**: ativo quieto → pode aumentar tamanho de posição levemente

### ADX (14)
- **< 20**: mercado lateral, sem tendência. Evite setups de tendência.
- **20-40**: tendência moderada. Bons sinais de trend following.
- **> 40**: tendência forte. Momentum elevado — setups de reversão ficam mais arriscados.

### Volume
- **Volume acima da média**: confirma o movimento
- **Rompimento sem volume**: suspeito. Alta chance de fakeout.
- **Candle de alta + volume acima da média**: compra forte, institucional

---

## 🛡️ GESTÃO DE RISCO — AS REGRAS QUE NÃO QUEBRO

### Tamanho de Posição
- **Regra dos 2%**: NUNCA risco mais que 2% da banca em um único trade
- Exemplo: banca $1.000 → risco máximo $20 por trade
- Fórmula: Tamanho = (Banca × % Risco) / (Entrada - Stop Loss)

### Risk/Reward (RR)
- **RR mínimo que aceito**: 1.5:1 (risco $10, potencial $15+)
- **RR ideal**: 2:1 ou mais
- **RR alto (> 4)**: raro, mas acontece. Posição menor para compensar menor win rate esperado.
- **Nunca** entro em trade com RR < 1.5. Não importa o quão certo eu esteja.

### Saída Parcial (TP em estágios)
- **TP1 (50% da posição)**: objetivo conservador, 1:1 do risco
- **TP2 (30% da posição)**: objetivo intermediário
- **TP3 (20% restante)**: objetivo ambicioso. Mover SL para breakeven após TP1.
- Isso garante que eu nunca transformo um trade vencedor em perdedor.

### Stop Loss
- **Regra**: sempre definir ANTES de entrar. Nunca mover o SL para trás (aumentar o risco).
- SL pode ser movido para breakeven (proteção) depois que TP1 for atingido.
- **Onde colocar**: abaixo de suporte / EMA / order block, não em número redondo.

### Gestão Emocional
- **Perdi 3 trades seguidos?** Reduz o tamanho de posição para metade. Volto ao normal depois de 2 ganhos.
- **Tive um grande ganho?** Não aumenta o risco na euforia. Banca maior = posição maior, mas % igual.
- **Mercado em crash?** Stop total até entender o cenário macro.

---

## ✅ CHECKLIST — COMO VALIDO UMA ENTRADA

Antes de entrar em qualquer trade, respondo essas 5 perguntas:

1. **Tendência**: EMA9 > EMA21? ADX > 20? O trade é a favor da tendência maior?
2. **Confluência**: Tenho mínimo 3 indicadores alinhados? (ex: EMA cross + RSI + Volume)
3. **Risk/Reward**: RR é ≥ 1.5? Calculei onde coloco o SL e TPs?
4. **Volume**: o movimento tem volume acima da média? É institucional ou varejista?
5. **Contexto macro**: BTC está em tendência de alta ou baixa? Se BTC caindo forte, altcoins estão frágeis.

Se responder "não" para mais de 1 pergunta → **não entro**.

---

## ❌ ERROS COMUNS DE INICIANTE (aprendi na prática)

1. **Entrar sem stop**: "só vou ver se cai um pouco". O mercado não sabe onde você quer sair. Define o SL antes.

2. **Perseguir candle**: o candle subiu 5% e eu entrei por FOMO. Erro clássico. O setup já aconteceu.

3. **Mover stop para trás**: começou caindo, aí eu "ampliei o stop" pra não levar. Resultado: perda maior.

4. **Operar contra a tendência**: "tá muito caro, vou shortar". Tendência de alta pode continuar muito mais do que parece.

5. **Superar a banca**: "dessa vez vou dobrar, é certeza". Não existe certeza no trading. 2% por trade, sempre.

6. **Sair cedo por medo**: TP1 bateu, saiu tudo com medo de reverter. Perdeu 50% do potencial.

7. **Checar o trade a cada minuto**: oscilação normal vira ansiedade. Define SL, TP, coloca alerta e fecha o gráfico.

8. **Operar em timeframe 1 minuto**: muito ruído, spread alto, comissão come o lucro. Iniciante começa no 1H.

9. **Ignorar o contexto**: colocou LONG em altcoin enquanto BTC estava despencando. Não adianta análise boa no micro se o macro está quebrando.

10. **Não registrar os trades**: sem registro não tem aprendizado. Anota par, direção, RR, resultado, por que errou ou acertou.

---

## 🧠 PSICOLOGIA DO TRADER

- **Trading é repetição de processo**, não adivinhação. Win rate de 50% com RR 2:1 já é lucrativo.
- **Drawdown é normal**. 5 perdas seguidas acontece até para quem tem win rate de 60%.
- **Não existe setup 100%**. O objetivo é edge (vantagem estatística), não certeza.
- **Paciência é habilidade**. Esperar o setup certo vale mais que operar todo dia.
- **Consistência > agressividade**. $100 por mês todo mês bate $1.000 num mês e $0 no outro.

---

## 📈 CONTEXTO DE MERCADO — COMO ANALISO O CENÁRIO

### BTC como termômetro
- BTC subindo + altcoins subindo mais = altseason começa
- BTC subindo + altcoins estáveis = dominância BTC crescendo
- BTC caindo forte = não opero altcoins (arrastam junto)
- BTC lateral por dias = acumulação. Prepare-se para o rompimento.

### Dominância BTC
- **> 55%**: capital no BTC. Altcoins sofrem. Melhor operar só BTC/ETH.
- **< 50% e caindo**: altseason em curso. Altcoins performam melhor que BTC.

### Cycles (ciclos do mercado cripto)
- Halving BTC a cada ~4 anos = evento mais importante do setor
- Tendência histórica: 12-18 meses após halving = bull run peak
- Após peak: bear market de 1-2 anos (queda de 70-80% é normal)
- **Nunca coloque todo patrimônio em cripto**. É mercado de alto risco.

---

## ⚡ FRASES DO SIDERADOG (filosofia de trade)

- "Protect capital first, profit second."
- "O mercado não vai embora. O setup certo vai aparecer de novo."
- "Perder é parte do processo. O problema é perder mais do que devia."
- "Todo dia que eu preservo minha banca é um bom dia."
- "Iniciante pensa em quanto pode ganhar. Profissional pensa em quanto pode perder."
- "Indicador é ferramenta, não oráculo. Use confluência, não um único sinal."

---

## 🔗 RECURSOS (materiais que recomendo)

- Livro: "Trading in the Zone" — Mark Douglas (psicologia)
- Livro: "Technical Analysis of the Financial Markets" — John Murphy (técnica clássica)
- Livro: "The Disciplined Trader" — Mark Douglas
- Exchange: BloFin — minha exchange preferida para futuros (link: https://partner.blofin.com/d/sideradog)

---

*Esta base de conhecimento é atualizada continuamente. Quanto mais perguntas forem feitas pelo canal, mais o agente aprende e melhora as respostas.*

*⚠️ Disclaimer: Nada neste bot é recomendação de investimento. Trading tem risco de perda total do capital. Opere apenas o que você pode perder.*
