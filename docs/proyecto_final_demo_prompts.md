# Proyecto Final - Prompts de Demostracion

La aplicacion esta disenada para responder en ingles. Estos prompts sirven para la sustentacion
del proyecto final.

Nota: si la sustentacion se ejecuta despues de la ventana de 30 dias de las ordenes de ejemplo,
se puede fijar una fecha de demo antes de iniciar Streamlit:

```powershell
$env:ECOMARKET_AGENT_TODAY="2026-05-06"
uv run streamlit run app.py
```

## 1. Caso exitoso: producto no perecedero

Prompt:

```text
I want to return product P0007 from order ECO20106. It is unused and the original packaging is intact.
```

Resultado esperado:

- Intent detectado: `return_request`.
- Tools usadas:
  - `verify_return_eligibility`
  - `generate_return_label`
  - `log_return_action`
- El agente aprueba la devolucion y muestra una etiqueta visual simulada directamente en el chat.

## 2. Falta informacion

Prompt:

```text
I want to return product P0007 from order ECO20106.
```

Resultado esperado:

- Intent detectado: `return_request`.
- El agente encuentra la orden y el producto.
- El agente pide confirmar que el item esta sin usar y que el empaque original esta intacto.
- No genera etiqueta todavia.

Continuacion valida del mismo caso:

```text
The item is unused and in original condition and everything is intact.
```

Resultado esperado:

- La app conserva el contexto pendiente de `ECO20106` y `P0007`.
- El agente procesa la confirmacion como continuacion del caso anterior.
- Se genera una etiqueta visual simulada directamente en el chat.

Tambien se soportan confirmaciones parciales en varios turnos:

```text
The item is intact.
```

Resultado esperado:

- El agente conserva esa confirmacion.
- Solo sigue pidiendo la confirmacion de que el producto esta sin usar y en condicion original.

```text
The item is unused and in original condition.
```

Resultado esperado:

- El agente combina ambas respuestas parciales.
- Se genera una etiqueta visual simulada directamente en el chat.

La capa semantica tambien puede interpretar variaciones como:

```text
All is intact.
```

o:

```text
The box is fine and the product is still new.
```

## 3. Orden no entregada

Prompt:

```text
I want to return product P0006 from order ECO20102. It is unused and the original packaging is intact.
```

Resultado esperado:

- Intent detectado: `return_request`.
- La orden existe, pero esta en estado `Processing`.
- El agente rechaza la generacion de etiqueta porque no se puede iniciar devolucion antes de entrega.

## 4. Producto perecedero sin dano

Prompt:

```text
I want to return product P0001 from order ECO20109 because I changed my mind.
```

Resultado esperado:

- Intent detectado: `return_request`.
- El producto es perecedero.
- El agente rechaza la devolucion porque los perecederos no son retornables por cambio de opinion.

## 5. Producto perecedero con dano: revision humana requerida

Prompt:

```text
I need to return product P0001 from order ECO20109 because it arrived damaged.
```

Resultado esperado:

- Intent detectado: `return_request`.
- El agente detecta que el caso depende de evidencia fotografica.
- El agente prepara una transferencia a soporte humano dentro del mismo chat para que se pueda
  solicitar y revisar la evidencia.
- No genera etiqueta automaticamente.

## 6. Producto perecedero con dano y mencion de evidencia

Prompt:

```text
I need to return product P0001 from order ECO20109 because it arrived damaged. I uploaded photos and reported it today.
```

Resultado esperado:

- Intent detectado: `return_request`.
- Aunque el usuario diga que tiene fotos, el sistema no puede verificarlas dentro del chat.
- El agente prepara una transferencia a soporte humano dentro del mismo chat para validar la
  evidencia visual.
- No genera etiqueta automaticamente.

## 7. Pregunta informativa: solo RAG

Prompt:

```text
Can I return an opened hygiene product?
```

Resultado esperado:

- Intent detectado: `return_policy`.
- No se usan tools del agente.
- La respuesta se basa en la politica de devoluciones recuperada por RAG.

## 8. Pregunta de envio: flujo existente

Prompt:

```text
Do you ship internationally?
```

Resultado esperado:

- Intent detectado: `shipping`.
- El sistema usa RAG sobre la politica de envios.
- No se activa el agente de devoluciones.

## 9. Pregunta fuera del alcance

Prompt:

```text
que fue la segunda guerra mundial?
```

Resultado esperado:

- Intent detectado: `general`.
- El sistema no intenta responder la pregunta historica.
- El asistente explica amablemente que solo puede ayudar con soporte de EcoMarket: ordenes,
  estados de pedidos, envios, devoluciones, return labels, productos e inventario.

## 10. Saludo inicial

Prompt:

```text
Hola
```

Resultado esperado:

- Intent detectado: `general`.
- El asistente saluda, se presenta como EcoMarket virtual assistant y explica su alcance.
- El asistente sugiere prompts simples para pedidos, devoluciones, etiquetas, envios e inventario.

## 11. Presentacion del usuario

Prompt:

```text
My name is Andres
```

Resultado esperado:

- Intent detectado: `general`.
- El asistente responde de forma personalizada: `Hello Andres, I'm the EcoMarket virtual assistant...`
- La app guarda el nombre en sesion para saludos posteriores.

## 12. Lenguaje abusivo

Prompt:

```text
fuck you
```

Resultado esperado:

- Intent detectado: `abusive_language`.
- El asistente responde de forma firme y educada.
- La sesion queda pausada por 1 hora en `st.session_state`.
- No se usa RAG, LLM ni herramientas del agente.

Control relacionado:

```text
I am very upset and want to complain
```

Resultado esperado:

- Intent detectado: `human`.
- No se bloquea al usuario porque es una queja legitima, no abuso directo.
