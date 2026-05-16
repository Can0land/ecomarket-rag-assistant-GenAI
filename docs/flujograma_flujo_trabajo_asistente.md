# Flujograma del flujo de trabajo del asistente EcoMarket

Este documento resume que ocurre desde que el usuario escribe un mensaje en la interfaz
hasta que recibe una respuesta. Esta pensado para sustentacion presencial: primero muestra
el flujo general, luego las ramas por intencion y finalmente el subflujo del agente de
devoluciones.

## 1. Inicializacion de la aplicacion

Antes de que el usuario envie mensajes, Streamlit prepara la interfaz y carga la base de
conocimiento.

```mermaid
flowchart TD
    A[Inicio de la app Streamlit<br/>app.py] --> B[Configurar pagina<br/>titulo, icono, layout]
    B --> C[load_vectorstore con cache_resource]
    C --> D{Existe indice FAISS<br/>vectorstore/faiss_index?}
    D -->|Si| E[Cargar FAISS local<br/>load_vectorstore]
    D -->|No| F[Cargar documentos desde data]
    F --> F1[PDF politica devoluciones]
    F --> F2[PDF politica envios]
    F --> F3[Excel inventario]
    F --> F4[Excel catalogo]
    F --> F5[JSON ordenes]
    F1 --> G[Chunking<br/>391 caracteres, 45 overlap]
    F2 --> G
    F3 --> G
    F4 --> G
    F5 --> G
    G --> H[Crear embeddings<br/>all-MiniLM-L6-v2]
    H --> I[Construir y guardar indice FAISS]
    E --> J[Vectorstore listo]
    I --> J
    C -->|Error| K[Mostrar error en UI<br/>vectorstore = None]
    J --> L[Inicializar session_state]
    K --> L
    L --> M[messages, last_intent, last_sources,<br/>rag_used, pending_return_request,<br/>customer_name, blocked_until]
    M --> N[Renderizar sidebar y mensajes previos]
    N --> O[Esperar entrada del usuario<br/>st.chat_input]
```

Puntos clave para explicar:

- El vectorstore se carga una sola vez por sesion gracias a `@st.cache_resource`.
- Si el indice no existe, se construye desde los archivos de `data/`.
- Si la base vectorial falla, la app no se cae: algunas respuestas funcionan con datos
  estructurados o mensajes de degradacion.

## 2. Flujo principal desde mensaje hasta respuesta

```mermaid
flowchart TD
    A[Usuario escribe mensaje<br/>st.chat_input] --> B[Guardar mensaje del usuario<br/>st.session_state.messages]
    B --> C[Mostrar mensaje en el chat]
    C --> D{Chat bloqueado<br/>por lenguaje abusivo?}
    D -->|Si| E[Responder pausa temporal<br/>calcular minutos restantes]
    E --> F[Actualizar estado:<br/>intent=blocked, sin sources, rag_used=False]
    F --> G[Guardar respuesta del asistente]
    G --> H[Renderizar respuesta]
    H --> I[st.rerun]

    D -->|No| J{Hay devolucion pendiente<br/>en session_state?}
    J -->|Si| K{Mensaje parece continuacion?<br/>producto, confirmacion, packaging, etc.}
    K -->|Si| L[Construir effective_input<br/>con contexto acumulado]
    K -->|No| M[Usar user_input original]
    J -->|No| M
    L --> N[Extraer nombre del cliente<br/>si el mensaje lo contiene]
    M --> N

    N --> O[handle_message effective_input]
    O --> P[detect_intent<br/>router por keywords con prioridad]

    P --> Q{Intent detectado}

    Q -->|abusive_language| R[Respuesta firme y educada<br/>sin llamar RAG ni LLM]
    R --> R1[blocked_until = ahora + 1 hora<br/>limpiar devolucion pendiente]

    Q -->|human| S[Construir prompt de escalamiento<br/>build_human_prompt]
    S --> S1[LLM Gemma 2B via Ollama]

    Q -->|order_status| T{Hay tracking ECO...?}
    T -->|No| T1[Pedir numero de orden]
    T -->|Si| T2[Buscar orden en orders_enhanced.json]
    T2 --> T3{Orden existe?}
    T3 -->|No| T4[Informar que no se encontro]
    T3 -->|Si| T5[Recuperar contexto RAG opcional<br/>top-k=3]
    T5 --> T6[build_order_prompt<br/>orden + contexto + ejemplos]
    T6 --> T7[LLM Gemma 2B]
    T7 --> T8[Agregar tarjeta estructurada<br/>format_order_response]

    Q -->|return_request| U[Recuperar politica de devoluciones<br/>RAG filter returns_policy top-k=4]
    U --> U1[Si no hay contexto,<br/>buscar en toda la base]
    U1 --> U2[run_return_agent]

    Q -->|return_policy| V[Recuperar returns_policy<br/>fallback a busqueda general]
    V --> V1[build_return_prompt]
    V1 --> V2[LLM Gemma 2B]

    Q -->|shipping| W[Recuperar shipping_policy<br/>fallback a busqueda general]
    W --> W1[build_shipping_prompt]
    W1 --> W2[LLM Gemma 2B]

    Q -->|inventory| X[Buscar producto por ID P0001<br/>o por nombre en Excel]
    X --> X1[Recuperar contexto RAG general]
    X1 --> X2{Hay producto o contexto?}
    X2 -->|No| X3[Pedir ID o nombre del producto]
    X2 -->|Si| X4[build_inventory_prompt<br/>registro estructurado + RAG]
    X4 --> X5[LLM Gemma 2B]
    X5 --> X6[Agregar Product record<br/>si hubo dato estructurado]

    Q -->|product| Y[Recuperar product_catalog<br/>fallback a busqueda general]
    Y --> Y1[build_product_prompt]
    Y1 --> Y2[LLM Gemma 2B]

    Q -->|general| Z{Saludo o nombre detectado?}
    Z -->|Si| Z1[Responder saludo personalizado]
    Z -->|No| Z2{Pregunta fuera del alcance<br/>de EcoMarket?}
    Z2 -->|Si| Z3[Responder limites del asistente]
    Z2 -->|No| Z4[Recuperar contexto RAG general]
    Z4 --> Z5[build_general_prompt]
    Z5 --> Z6[LLM Gemma 2B]

    R1 --> AA[Actualizar last_intent,<br/>last_sources, rag_used]
    S1 --> AA
    T1 --> AA
    T4 --> AA
    T8 --> AA
    U2 --> AA
    V2 --> AA
    W2 --> AA
    X3 --> AA
    X6 --> AA
    Y2 --> AA
    Z1 --> AA
    Z3 --> AA
    Z6 --> AA

    AA --> AB{Intent es return_request<br/>y falta informacion?}
    AB -->|Si| AC[Guardar pending_return_request<br/>tracking, producto, input acumulado]
    AB -->|No| AD[Limpiar o conservar segun caso]
    AC --> AE[Guardar respuesta del asistente]
    AD --> AE
    AE --> AF[Renderizar markdown y SVG si existe]
    AF --> AG[st.rerun para refrescar UI]
```

Puntos clave para explicar:

- La primera decision importante es si el chat esta bloqueado por abuso.
- Despues se reconstruye el contexto de una devolucion pendiente, para que respuestas cortas como
  "yes, unused and packaging intact" no se pierdan.
- El router es deterministico y usa prioridad:
  `abusive_language > human > return_request > order_status > return_policy > shipping > inventory > product > general`.
- No todos los caminos usan RAG. Algunos usan datos estructurados, respuestas estaticas o ambos.
- Cuando se usa LLM, el prompt incluye reglas de grounding para reducir alucinaciones.

## 3. Ramas por tipo de respuesta

```mermaid
flowchart LR
    A[Mensaje del usuario] --> B[Router de intenciones]
    B --> C[Respuesta estatica]
    B --> D[Datos estructurados]
    B --> E[RAG + LLM]
    B --> F[Agente con tools]

    C --> C1[abusive_language<br/>blocked<br/>saludo<br/>fuera de alcance<br/>faltan datos]

    D --> D1[order_service<br/>orders_enhanced.json]
    D --> D2[inventory_service<br/>inventory_200_products_named.xlsx]
    D1 --> D3[LLM + tarjeta de orden]
    D2 --> D4[LLM + registro de producto]

    E --> E1[retrieve_context_text]
    E1 --> E2[FAISS similarity_search_with_score]
    E2 --> E3[Contexto + sources]
    E3 --> E4[Prompt especifico por intent]
    E4 --> E5[Gemma 2B via Ollama]

    F --> F1[return_agent]
    F1 --> F2[verify_return_eligibility]
    F1 --> F3[generate_return_label]
    F1 --> F4[log_return_action]
    F2 --> F5[Respuesta aprobada,<br/>rechazada, incompleta o manual_review]
    F3 --> F6[SVG de etiqueta renderizado en Streamlit]
```

## 4. Subflujo del agente de devoluciones

Este es el flujo mas importante si te preguntan por agentes, tools y control de riesgo.

```mermaid
flowchart TD
    A[Intent return_request] --> B[Recuperar contexto de politica<br/>returns_policy con RAG]
    B --> C[run_return_agent]
    C --> D{Hay tracking ECO...?}
    D -->|No| E[Pedir numero de orden<br/>y producto]
    D -->|Si| F[Buscar orden<br/>get_order]
    F --> G{Orden existe?}
    G -->|No| H[Informar orden no encontrada]
    G -->|Si| I[Identificar producto en la orden]
    I --> J{Producto identificado?}
    J -->|No| K[Listar items de la orden<br/>pedir cual desea devolver]
    J -->|Si| L[Extraer contexto de devolucion]

    L --> L1[Reglas deterministicas:<br/>motivo, unused, packaging,<br/>foto, reporte 48h]
    L --> L2{Mensaje ambiguo<br/>con terminos semanticos?}
    L2 -->|Si| L3[LLM como parser JSON estrecho<br/>no decide elegibilidad]
    L2 -->|No| M[Contexto final]
    L3 --> M

    M --> N[Tool: verify_return_eligibility]
    N --> O{Resultado}

    O -->|eligible| P[Tool: generate_return_label]
    P --> Q[Tool: log_return_action<br/>return_label_generated]
    Q --> R[Respuesta aprobada<br/>RMA, label ID, tracking,<br/>instrucciones y SVG]

    O -->|needs_more_information| S[Tool: log_return_action<br/>return_information_needed]
    S --> T[Pedir confirmaciones faltantes]
    T --> U[Guardar pending_return_request<br/>para continuar conversacion]

    O -->|manual_review| V[Tool: log_return_action<br/>return_manual_review_required]
    V --> W[Explicar handoff humano<br/>por evidencia fotografica]

    O -->|not_eligible| X[Tool: log_return_action<br/>return_denied]
    X --> Y[Explicar rechazo<br/>con reglas de politica]

    O -->|error| Z[Responder error especifico<br/>orden/producto no valido]
```

Decisiones de elegibilidad que aplica la tool:

- La orden debe existir.
- El producto debe pertenecer a la orden.
- La orden debe estar en estado `Delivered`.
- La solicitud debe estar dentro de la ventana de 30 dias desde la entrega estimada.
- El item debe estar sin usar y con empaque/etiquetas/accesorios intactos.
- Perecederos solo se aceptan si hay error de EcoMarket: danado, defectuoso, incorrecto,
  deteriorado o expirado al llegar.
- Casos que requieren fotos no generan etiqueta automaticamente; pasan a revision humana.

## 5. Que se muestra finalmente al usuario

```mermaid
flowchart TD
    A[Respuesta generada o estatica] --> B[Actualizar session_state]
    B --> C[last_intent]
    B --> D[last_sources]
    B --> E[rag_used]
    B --> F[pending_return_request si aplica]
    B --> G[blocked_until si hubo abuso]
    B --> H[Agregar mensaje assistant<br/>a historial]
    H --> I{La respuesta contiene<br/>RETURN_LABEL_SVG_START?}
    I -->|Si| J[Separar markdown y SVG]
    J --> K[Renderizar SVG con components.html]
    I -->|No| L[Renderizar markdown normal]
    K --> M[st.rerun]
    L --> M
```

## 6. Guion breve para sustentarlo

1. El usuario escribe en Streamlit y el mensaje se guarda en `st.session_state.messages`.
2. Antes de procesar, la app revisa si el chat esta bloqueado por lenguaje abusivo.
3. Si hay una devolucion pendiente, el sistema reconstruye el mensaje efectivo con el contexto
   anterior.
4. `handle_message` llama al router de intenciones.
5. Segun la intencion, el sistema puede:
   - responder de forma estatica,
   - consultar datos estructurados,
   - recuperar contexto con FAISS,
   - construir un prompt y llamar a Gemma 2B,
   - o ejecutar el agente de devoluciones con tools.
6. El LLM no recibe libertad total: se le pasa contexto recuperado, datos autorizados y reglas
   para no inventar.
7. En devoluciones, la decision critica no la toma el LLM sino `verify_return_eligibility`.
8. La respuesta final se guarda, se muestra en la UI y la app se refresca con `st.rerun`.

## 7. Preguntas que probablemente te pueden hacer

**Que pasa si el usuario pregunta algo fuera de EcoMarket?**  
El flujo `general` revisa palabras del dominio. Si no encuentra relacion con soporte de
EcoMarket, responde que solo puede ayudar con pedidos, envios, devoluciones, productos e
inventario.

**Que pasa si el usuario no da el numero de orden?**  
En `order_status` se pide el tracking. En `return_request` se pide tracking y producto.

**Que pasa si la base vectorial no carga?**  
`vectorstore` queda como `None`. Algunas rutas siguen funcionando con datos estructurados o
mensajes de fallback; las rutas de politica usan contexto no disponible o respuestas de
degradacion.

**Que evita que el modelo invente una politica?**  
Los prompts incluyen una regla de grounding: responder solo con la informacion proporcionada y
decir que no hay suficiente informacion si el contexto no alcanza.

**Por que hay un agente en devoluciones?**  
Porque no solo responde texto: verifica elegibilidad, puede generar una etiqueta simulada y deja
auditoria en logs. Esa accion requiere tools y reglas deterministicas.

**Donde queda la trazabilidad?**  
Las fuentes RAG se guardan en `last_sources` para la barra lateral, y las acciones del agente se
registran en `logs/return_agent_actions.jsonl`.
