# Proyecto Final - Fase 1: Arquitectura del Agente

## Objetivo

El objetivo del proyecto final es extender el asistente RAG de EcoMarket para que no solo
responda preguntas, sino que tambien pueda ejecutar una tarea operativa simulada: iniciar
una devolucion, verificar elegibilidad y generar una etiqueta de retorno.

La interfaz y las respuestas al usuario se mantienen en ingles, porque la base de conocimiento,
los datos y los prompts principales del repositorio estan construidos para operar en ese idioma.

## Extension de la arquitectura RAG

La arquitectura original ya separaba tres responsabilidades:

- Enrutamiento por intencion.
- Recuperacion RAG con FAISS para politicas, catalogo y contexto.
- Consultas estructuradas para pedidos e inventario.

La extension agrega una ruta nueva llamada `return_request`. Esta ruta se activa cuando el
usuario no solo pregunta por la politica, sino que solicita una accion como generar una etiqueta
o iniciar una devolucion.

```text
User message
    |
    v
Intent router
    |
    |-- return_policy  -> RAG answer about policy
    |
    |-- return_request -> Return Automation Agent
                           |
                           |-- retrieve return policy context
                           |-- identify order and product
                           |-- verify_return_eligibility
                           |-- generate_return_label, if eligible
                           |-- log_return_action
                           |-- format final answer
```

Esta decision conserva el RAG como fuente de contexto documental, pero evita que el LLM tome
decisiones criticas por si solo. El agente usa herramientas deterministicas para decidir si una
etiqueta puede generarse.

## Marco de agentes seleccionado

Se selecciono LangChain por tres razones:

- El proyecto ya usa LangChain para documentos, FAISS y embeddings.
- LangChain permite definir tools reutilizables mediante `StructuredTool`.
- Evita introducir un segundo framework como LlamaIndex, reduciendo complejidad y riesgo de
  integracion.

El agente implementado es un agente hibrido: usa tools de LangChain, pero la orquestacion es
deterministica. Esto es apropiado para un flujo sensible, porque generar una etiqueta de devolucion
es una accion operativa y debe estar controlada por reglas verificables.

## Tools definidas

### 1. `verify_return_eligibility`

Verifica si un producto de una orden puede devolverse.

Entradas principales:

- `tracking_number`
- `product_id`
- `return_reason`
- `unused`
- `packaging_intact`
- `photo_evidence`
- `reported_within_48h`

Respuesta:

```json
{
  "status": "eligible",
  "eligible": true,
  "shipping_cost_responsibility": "customer",
  "reasons": ["The request is within the 30-day return window."],
  "missing_information": [],
  "warnings": []
}
```

La tool usa las reglas de la politica de devoluciones:

- Ventana de 30 dias desde entrega.
- Producto sin usar y con empaque original intacto.
- Productos perecederos solo son retornables si llegaron danados, defectuosos, vencidos,
  deteriorados o incorrectos.
- Reclamos por daño o producto incorrecto requieren evidencia fotografica y reporte dentro de
  48 horas.
- Como el prototipo actual no permite cargar ni validar imagenes, esos reclamos no se aprueban
  automaticamente. El agente devuelve `manual_review` y prepara un handoff a soporte humano
  para que el caso continue en el mismo chat.
- Las ordenes internacionales pueden tener restricciones o costos adicionales.

Como el dataset no contiene fecha real de entrega, el agente usa `estimated_delivery` como proxy
solamente cuando la orden esta en estado `Delivered`.

### 2. `generate_return_label`

Genera una etiqueta simulada para una devolucion elegible. La respuesta incluye datos
estructurados y un SVG renderizable directamente en el chat de Streamlit.

Respuesta:

```json
{
  "status": "generated",
  "return_authorization_id": "RMA-ECO20106-P0007",
  "label_id": "RTL-1234ABCD",
  "carrier": "EcoShip Returns",
  "tracking_number": "RET1234ABCD",
  "dropoff_deadline": "2026-05-20",
  "label_svg": "<svg>...</svg>"
}
```

Esta tool solo se invoca si `verify_return_eligibility` devuelve `eligible`.

### 3. `log_return_action`

Registra las acciones del agente en `logs/return_agent_actions.jsonl`.

El registro incluye:

- Timestamp.
- Accion ejecutada.
- Orden.
- Producto.
- Estado.
- Resultado de la herramienta.

Esta tool soporta observabilidad y auditoria del agente.

## Flujo de trabajo

```text
1. El usuario solicita iniciar una devolucion.
2. El router clasifica el mensaje como return_request.
3. El sistema recupera contexto de la politica de devoluciones mediante RAG.
4. El agente extrae numero de orden y producto.
5. Si el usuario responde en varios turnos, la app acumula las confirmaciones parciales del caso.
6. Una capa semantica acotada con LLM interpreta variaciones como "all is intact",
   "the box is fine" o "still new" y las convierte en campos estructurados.
7. Si falta informacion, el agente pregunta por los datos faltantes.
8. Si la orden o producto no existen, el agente responde con error controlado.
9. El agente invoca verify_return_eligibility.
10. Si la devolucion no es elegible, responde con razon y base de politica.
11. Si el caso depende de evidencia fotografica, no genera etiqueta y prepara un handoff a
    soporte humano en el mismo chat.
12. Si falta informacion, pide confirmacion especifica.
13. Si es elegible, invoca generate_return_label.
14. El agente registra la accion con log_return_action.
15. El usuario recibe la autorizacion, etiqueta e instrucciones solo en casos elegibles automaticos.
```

## Justificacion de seguridad

El LLM no decide si una devolucion es aprobada. Su rol en el sistema general sigue siendo redactar
respuestas y explicar informacion recuperada. En el flujo de agente, el LLM solo puede ayudar a
interpretar confirmaciones del usuario como datos estructurados. La decision final se toma con
datos estructurados y reglas explicitas. Esto reduce el riesgo de aprobaciones incorrectas,
alucinaciones o acciones sin trazabilidad.
