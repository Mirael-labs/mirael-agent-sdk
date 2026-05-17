# Mirael Labs — Business Model

## Resumen ejecutivo

Mirael Agent SDK permite a protocolos DeFi desplegar agentes AI de soporte al
cliente en minutos. El agente entiende los docs del protocolo y lee las
posiciones reales del usuario on-chain. Primero vendemos el servicio (setup +
retainer mensual). Después lo productizamos en SaaS.

---

## El problema de mercado

### Escala del problema

| Protocolo | Discord Members | Preguntas/día (est.) | Costo soporte humano/mes |
|---|---|---|---|
| Aave | 180K | ~500 | $8,000-15,000 |
| GMX | 95K | ~300 | $5,000-10,000 |
| Hyperliquid | 120K+ | ~400 | $7,000-12,000 |
| Protocolo mediano (50K usuarios) | 50K | ~150 | $3,000-6,000 |

El 80% de las preguntas son repetidas:
- "¿Por qué me cobran funding?"
- "¿A qué precio me liquidan?"
- "¿Cómo funciona el health factor?"
- "¿Por qué no puedo abrir más posiciones?"

**Ninguna herramienta existente** puede responder "¿*tu* posición específica está
en riesgo ahora mismo?" porque requiere leer el wallet on-chain en tiempo real.

### Tamaño del mercado

- **200+ protocolos DeFi activos** en Arbitrum + Ethereum
- **Top 20 protocolos** = mercado inmediato (~$2-4M ARR posible)
- **Protocolo mediano** tiene 50K-500K usuarios y un equipo de 10-30 personas
- **Pain point validado**: ningún protocolo tiene soporte 24/7 satisfactorio

---

## Propuesta de valor

### Para el protocolo
- Reduce tickets de soporte repetido en 70-80%
- Soporte 24/7 sin contratar más personas
- Respuestas consistentes y correctas (no alucinaciones — RAG grounded)
- Alertas proactivas antes de que los usuarios se liquiden = menos churn

### Para el usuario final
- Respuesta inmediata a cualquier hora
- Ve *sus* posiciones reales, no ejemplos genéricos
- Aviso antes de liquidación (feature `/monitor`)

### Diferenciador clave
> "Any chatbot can explain *what* a health factor is.  
> Only Mirael can say *your* health factor is 1.42 right now — reduce debt."

---

## Modelo de negocio

### Fase 1 — Services-first (ahora → Q3 2026)

**Por qué services-first:**
- Valida el producto con clientes reales antes de productizar
- Cash flow positivo desde el primer cliente
- Aprende exactamente qué necesita cada protocolo antes de hacer el SaaS

**Estructura de precios:**

| Componente | Precio | Descripción |
|---|---|---|
| Setup & integración | $10,000 - $15,000 (one-time) | Configuración, ingest de docs del protocolo, deploy del bot en su Discord/Telegram, pruebas |
| Retainer mensual | $2,000 - $3,000/mes | Mantenimiento, actualización de docs, mejoras, soporte prioritario |
| Protocolo enterprise | $5,000+/mes | Multi-canal + analytics + integraciones custom |

**Desglose del setup ($12K promedio):**
- Ingest de toda la documentación del protocolo: 2-3 días
- Configuración y testing del agente: 2 días
- Deploy en Discord/Telegram del cliente: 1 día
- Fine-tuning de prompts y tono: 1-2 días
- Entrega y capacitación al equipo: 1 día

**Unit economics (cliente $12K setup + $2.5K/mes):**
- Año 1 ingresos: $12K + ($2.5K × 12) = **$42,000/cliente**
- Costo variable (APIs Anthropic + infra): ~$200-300/mes
- Margen bruto: ~90%

### Fase 2 — SaaS productizado (Q4 2026 →)

Una vez validados 5+ clientes services, lanzar self-serve:

| Plan | Precio/mes | Para quién |
|---|---|---|
| **Starter** | $299 | Protocolos pequeños, <50K usuarios, 1 canal |
| **Growth** | $799 | Protocolos medianos, <500K usuarios, Discord + Telegram |
| **Scale** | $1,999 | Protocolos grandes, >500K usuarios, multi-canal + analytics |
| **Enterprise** | Custom | Top 20 protocolos, SLA, on-premise, integraciones custom |

**Proyección MRR (escenario conservador):**

| Mes | Clientes services | MRR services | Clientes SaaS | MRR SaaS | MRR Total |
|---|---|---|---|---|---|
| Jun 2026 | 1 | $2,500 | 0 | $0 | $2,500 |
| Sep 2026 | 3 | $7,500 | 0 | $0 | $7,500 |
| Dic 2026 | 5 | $12,500 | 5 | $2,500 | $15,000 |
| Mar 2027 | 5 | $12,500 | 20 | $10,000 | $22,500 |
| Jun 2027 | 5 | $12,500 | 50 | $30,000 | $42,500 |

**Breakeven:** ~mes 4-5 con 3 clientes services activos.

---

## Go-to-Market

### Canales (en orden de prioridad)

**1. Buildathon + grants (ahora)**
- Arbitrum Open House London Buildathon — $20K si ganamos
- Visibilidad con toda la comunidad Arbitrum
- Credibilidad para llamadas de ventas

**2. Comunidad DeFi directa**
- Target: project managers / community managers de protocolos en Arbitrum
- Mensaje: "¿Cuánto tiempo pasa tu equipo respondiendo las mismas preguntas en Discord?"
- Canal: Twitter/X DM, LinkedIn, Discord DMs

**3. Eventos (calendario 2026-2027)**
- ETH México (Jun 2026) — networking con builders LATAM
- LABITCONF Argentina (Nov-Dic 2026) — fundraise + partnerships
- Aleph Hub Argentina — presencia en la escena cripto LATAM
- Lisboa / São Paulo (Q1 2027) — expansión internacional

**4. Inbound (después del buildathon)**
- GitHub repo open-source → desarrolladores que quieren implementarlo ellos mismos
- README con demo video → protocolos que ven el producto en acción

### Pitch en una oración

> "Mirael hace que tu protocolo DeFi tenga un agente AI que responde preguntas
> de soporte 24/7 — y sabe exactamente qué posiciones tiene cada usuario
> en tiempo real."

---

## Ventaja competitiva (moat)

| Capacidad | Mirael | ChatGPT/Claude genérico | Intercom/Zendesk AI | Competidor ad-hoc |
|---|---|---|---|---|
| Lee posiciones on-chain en tiempo real | ✅ | ❌ | ❌ | Difícil |
| RAG sobre docs del protocolo | ✅ | ❌ | Parcial | Posible |
| Alertas proactivas (antes de liquidación) | ✅ | ❌ | ❌ | Difícil |
| Multi-chain (HL + Arbitrum) | ✅ | ❌ | ❌ | Muy difícil |
| Open-source SDK | ✅ | N/A | ❌ | N/A |
| Setup en horas, no semanas | ✅ | N/A | ❌ | ❌ |

El moat real es la combinación de **RAG + contexto on-chain + historial de
conversación**. Cualquiera puede hacer un chatbot con Claude. Nadie más tiene
el pipeline completo integrado con múltiples chains.

---

## Uso del grant de $20K

| Destino | Monto | Para qué |
|---|---|---|
| Primeros 3 meses de infra (Anthropic API + Qdrant Cloud + VPS) | $2,000 | Escalar sin preocupaciones |
| Outreach a 50 protocolos en Arbitrum | $1,000 | Templates, cold email, herramientas |
| Viaje ETH México + LABITCONF | $3,000 | Networking en persona, cerrar deals |
| Desarrollo: GMX reader + Vertex reader | $4,000 | Expandir el moat a más protocolos Arbitrum |
| Desarrollo: dashboard analytics para protocolos | $5,000 | Feature que justifica tier Growth/Scale |
| Runway personal (3 meses) | $5,000 | Poder trabajar full-time en esto |

**Resultado esperado con el grant:**
- 3 clientes pagando ($7,500/mes) antes de acabar el grant
- GMX + Vertex readers listos = doble el mercado addressable en Arbitrum
- Analytics dashboard listo para lanzar SaaS Q4 2026

---

## Modelos de negocio adicionales

### Modelo 2 — API de contexto on-chain (B2B2C)

**Qué es:** En vez de vender el bot completo, vender acceso a la API de contexto
on-chain como servicio. Protocolos integran el endpoint en sus propias apps.

```
GET /api/v1/context?wallet=0x...&protocol=aave-arbitrum
→ {health_factor: 1.42, collateral: 8200, positions: [...]}
```

**Precio:** $0.001-0.005 por query. Con 1M queries/mes = $1K-5K/mes pasivo.  
**Por qué funciona:** Muchos equipos quieren el dato, no el bot completo.  
**Cuándo lanzar:** Cuando tengamos 3+ clientes services validando la demanda.

---

### Modelo 3 — Revenue share con protocolos

**Qué es:** En vez de cobrar mensual fijo, cobrar un % del valor que el bot
genera — por ejemplo, un % de las liquidaciones que el bot ayudó a evitar.

**Ejemplo:** Si el bot alerta a 100 usuarios antes de liquidación y cada uno
tenía $5K en riesgo → $500K de capital protegido → Mirael cobra 0.1% = $500.

**Por qué es atractivo para el protocolo:**
- Sin costo fijo — solo pagan si el bot funciona
- Alinea los incentivos perfectamente
- Más fácil de vender ("te cuesta $0 si no funciona")

**Riesgo:** Difícil de medir y verificar. Mejor como modelo complementario al
retainer mensual, no como reemplazo.

---

### Modelo 4 — White-label para protocolos grandes

**Qué es:** El protocolo grande quiere "su" AI, no "Mirael Agent". Vender una
versión completamente branded de la misma tecnología.

**Ejemplo:** Aave lanza "Aave AI" en su Discord — powered by Mirael pero sin
mencionar Mirael. Contrato $50-100K/año.

**Cuándo aplica:** Protocolos con >500K usuarios y brand equity fuerte que no
quieren asociar su nombre con un third-party.

---

### Modelo 5 — Agente de trading (expansión natural)

**Qué es:** Evolución del bot de soporte hacia un bot que puede *ejecutar*
acciones, no solo responder preguntas.

```
Usuario: "cierra mi posición de BTC si el health factor baja de 1.3"
Bot: "Configurado. Te avisaré y cerraré automáticamente."
```

**Por qué es el siguiente paso natural:**
- Ya tenemos el contexto on-chain en tiempo real
- Ya tenemos el historial de conversación
- Solo falta conectar los wallet adapters para firmar transacciones

**Timing:** Fase 3 (2027). Requiere integrar Account Abstraction o safe wallets.
El mercado de bots de trading DeFi es de $100M+.

---

### Modelo 6 — Datos de conversación anonimizados

**Qué es:** Los datos de qué preguntan los usuarios son extremadamente valiosos
para los protocolos (entienden qué confunde a sus usuarios, qué features piden,
qué problemas tienen).

**Producto:** Dashboard de analytics para el protocolo:
- "Las 20 preguntas más frecuentes esta semana"
- "El 34% de los usuarios pregunta sobre liquidación antes de su primera posición"
- "Spike de preguntas sobre funding el martes — correlacionado con el precio"

**Precio:** Incluido en el plan Growth ($799/mes) como diferenciador.

---

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Mitigación |
|---|---|---|
| Anthropic sube precios | Media | Arquitectura permite cambiar a otro LLM en horas |
| Protocolo grande construye in-house | Baja | Costo > 6 meses desarrollo, nosotros ya estamos |
| DeFi bear market reduce usuarios | Media | Protocolos siguen necesitando soporte aunque el mercado baje |
| Competidor bien financiado entra | Media | 6+ meses de ventaja, open-source genera network effect |

---

## Por qué Mael / Mirael Labs

- **Background DeFi + ML**: construyó plataformas de trading, agentes AI, y tools DeFi
- **LATAM**: primera empresa de este tipo enfocada en el mercado hispanohablante de crypto (Ecuador, Colombia, México, Argentina = millones de usuarios DeFi)
- **Solo founder eficiente**: sin overhead, 100% del capital va a producto
- **Open-source credibility**: el SDK en GitHub muestra calidad del código (193 tests, mypy strict, 0 violations)
