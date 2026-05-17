# Video Demo Script — Mirael Agent SDK
## Sin voz — solo texto en pantalla + música de fondo

**Duración objetivo:** 2:00 - 2:30 minutos  
**Herramienta:** OBS Studio (gratis) + cualquier editor (CapCut, DaVinci, iMovie)  
**Sin narración** — todo se comunica con texto overlay

---

## Setup antes de grabar

1. Abre el bot: `uv run python examples/discord_demo/bot.py`
2. Abre Discord en el navegador → tu servidor
3. Ten el README del repo abierto en otra pestaña
4. Usa **tema oscuro** en todo (Discord dark, browser dark)

---

## Escenas y textos en pantalla

### Escena 1 — [0:00 - 0:15] Título

**Pantalla:** Fondo negro / dark  
**Texto overlay (grande, centrado):**
```
Mirael Agent SDK

AI customer support agents
for DeFi protocols on Arbitrum

🔗 github.com/Mirael-labs/mirael-agent-sdk
```

---

### Escena 2 — [0:15 - 0:35] El problema

**Pantalla:** Screenshot de un Discord con muchas preguntas repetidas (busca uno público)  
**Texto overlay:**
```
DeFi protocols spend $5K-15K/month
on support teams answering the same questions.

"Why is my health factor dropping?"
"Am I going to get liquidated?"
"Why am I paying so much in funding?"

Generic AI chatbots can't help —
they don't see the user's actual wallet.
```

---

### Escena 3 — [0:35 - 1:10] Demo en Discord

**Pantalla:** Discord, ventana del bot  

**Acción 1:** Escribe lentamente y envía:
```
/ask what is the funding rate on Hyperliquid and why does it matter?
```

**Texto overlay (mientras responde):**
```
Bot reads 37 chunks of Hyperliquid documentation
via semantic search (RAG).

Answer grounded in real docs — not hallucinated.
```

**Acción 2:** Escribe:
```
/ask how does Aave V3 on Arbitrum calculate liquidation?
```

**Texto overlay:**
```
Aave V3 on Arbitrum — Arbitrum-native integration.

Pool contract: 0x794a61358D6845594F94dc1DB02A252b5b4814aD
```

**Acción 3:** Escribe:
```
/monitor 0x65bf83b7B8B3370bf2Dc59cdF95BfE221d064Fc2
```

**Texto overlay:**
```
/monitor — the killer feature.

Bot polls the wallet every 60 seconds.
DMs the user BEFORE liquidation — not after.
```

---

### Escena 4 — [1:10 - 1:30] Arquitectura (30 segundos)

**Pantalla:** El diagrama del README o una imagen simple que hagas

**Texto overlay:**
```
User (Discord / Telegram)
         ↓
   Mirael Agent (Claude claude-sonnet-4-5)
         ├── RAG → Qdrant → bge-large (local, free)
         ├── HyperliquidReader → Hyperliquid L1
         └── AaveV3Reader → Arbitrum mainnet

1 API key required: Anthropic
Setup time: < 1 hour
```

---

### Escena 5 — [1:30 - 1:50] Calidad del código

**Pantalla:** Terminal mostrando los tests pasando

**Comando a ejecutar (y grabar):**
```bash
pytest tests/unit/ -q --no-cov
# → 193 passed
```

**Texto overlay:**
```
193 unit tests · 19 E2E tests (real Anthropic API)
17 integration tests (Qdrant Cloud + Hyperliquid mainnet)

mypy strict ✅  ruff 0 violations ✅  bandit 0 issues ✅
```

---

### Escena 6 — [1:50 - 2:10] Business model

**Pantalla:** SUBMISSION.md abierto o slide simple

**Texto overlay:**
```
Business model: services-first → SaaS

Setup:    $10K-15K one-time
Retainer: $2K-3K/month
Margin:   ~90%

Target: 3 clients by September → $7,500 MRR
SaaS launch: Q4 2026

ICP: DeFi protocols on Arbitrum, 100K+ users
```

---

### Escena 7 — [2:10 - 2:30] Cierre

**Pantalla:** Fondo oscuro, logo/branding  
**Texto overlay:**
```
Mirael Agent SDK

Open-source · MIT License
github.com/Mirael-labs/mirael-agent-sdk

Built by Mael De La Hoz
Mirael Labs · Bucaramanga, Colombia

Built for the Arbitrum ecosystem 🔵
```

---

## Música de fondo

Busca en YouTube: "lofi chill background music no copyright"  
O usa: epidemic sound / pixabay music (gratis)  
Volumen: bajo, que no distraiga del texto

## Tips de edición

- **Fuente**: Inter o cualquier sans-serif, blanco sobre oscuro
- **Transiciones**: fade negro entre escenas (0.3s)
- **Texto**: aparece con fade in, desaparece con fade out
- **Zoom**: cuando muestres código, haz zoom 125-150%
- **Duración de cada texto**: mínimo 3 segundos para que se pueda leer

## Herramienta más fácil para editar

**CapCut** (gratis, Windows/Mac/móvil):
1. Importa el video grabado
2. Clic en "Text" → escribe los textos
3. Ajusta timing arrastrando los clips
4. Exporta en 1080p

---

*Tiempo estimado para grabar + editar: 1.5-2 horas*
