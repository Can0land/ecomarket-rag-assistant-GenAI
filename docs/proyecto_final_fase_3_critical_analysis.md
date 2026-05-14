# Proyecto Final - Fase 3: Analisis Critico y Mejoras

## Riesgos eticos y de seguridad

Agregar un agente cambia el riesgo del sistema: antes el asistente solo respondia, ahora puede
ejecutar una accion simulada. Esto obliga a controlar mejor las decisiones.

### Riesgo 1: aprobacion incorrecta de devoluciones

Un LLM podria aprobar una devolucion que no cumple la politica, por ejemplo un producto perecedero
sin evidencia de daño.

Mitigacion:

- La decision de elegibilidad no la toma el LLM.
- `verify_return_eligibility` aplica reglas deterministicas.
- La capa LLM solo interpreta variaciones linguisticas de las confirmaciones del usuario y las
  convierte en campos booleanos; no autoriza devoluciones por si misma.
- La etiqueta solo se genera si la respuesta estructurada indica `eligible`.
- Los reclamos que dependen de evidencia fotografica quedan en `manual_review`. El prototipo
  prepara un handoff a soporte humano para que la evidencia pueda revisarse antes de decidir
  elegibilidad.

### Riesgo 2: generacion de etiquetas con datos incompletos

El agente podria actuar sin tener orden, producto, condicion o evidencia suficiente.

Mitigacion:

- Si falta numero de orden o producto, el agente pregunta antes de actuar.
- Si el caso requiere evidencia visual, el agente no genera etiqueta y prepara una transferencia
  a soporte humano.
- Las respuestas distinguen claramente entre exito, rechazo, falta de informacion y revision
  manual.

### Riesgo 3: abuso del proceso de devoluciones

Un usuario podria intentar generar multiples devoluciones fraudulentas.

Mitigacion propuesta:

- Registrar cada accion en un log.
- Agregar en produccion un contador de solicitudes por cliente, producto y periodo.
- Escalar automaticamente patrones de abuso a revision humana.

### Riesgo 4: privacidad y manejo de datos

Las ordenes y devoluciones contienen informacion operacional del cliente.

Mitigacion:

- El prototipo usa datos simulados.
- En produccion se deberia evitar incluir datos sensibles en prompts.
- Los logs deben anonimizar datos personales y tener politicas de retencion.

### Riesgo 5: exceso de autonomia

Un agente no deberia ejecutar acciones irreversibles sin control.

Mitigacion:

- La etiqueta generada es simulada.
- La accion queda auditada.
- Acciones futuras como reembolsos reales deberian requerir confirmacion humana o doble
  validacion.

### Riesgo 6: lenguaje abusivo y seguridad conversacional

El sistema debe diferenciar entre clientes frustrados con un problema real y usuarios que inician
la conversacion con lenguaje abusivo directo. Bloquear cualquier emocion negativa seria injusto,
pero permitir abuso directo puede deteriorar la experiencia y el entorno de soporte.

Mitigacion:

- El router incluye un intent `abusive_language`.
- Si se detecta lenguaje abusivo directo, la sesion se pausa durante 1 hora.
- El usuario recibe una respuesta firme pero educada, invitandolo a intentar de nuevo con lenguaje
  respetuoso.
- Las quejas o frustraciones legitimas siguen usando el flujo `human`, no se bloquean
  automaticamente.
- En el prototipo el bloqueo vive en `st.session_state`; en produccion deberia integrarse con una
  capa de trust & safety mas robusta.

## Observabilidad

El sistema agrega observabilidad mediante `log_return_action`, que escribe eventos en
`logs/return_agent_actions.jsonl`.

Eventos registrados:

- `return_label_generated`
- `return_information_needed`
- `return_manual_review_required`
- `return_denied`

Cada evento contiene:

- Timestamp UTC.
- Orden.
- Producto.
- Estado final.
- Resultado de la tool.

## Monitoreo propuesto para produccion

Para un entorno real se recomienda:

- Dashboard con tasa de aprobacion, rechazo y casos incompletos.
- Alertas cuando aumenten los rechazos, errores o solicitudes repetidas.
- Muestreo de conversaciones para auditoria de calidad.
- Metricas por herramienta: latencia, errores y frecuencia de uso.
- Trazabilidad por version de politica y version del agente.

## Propuestas de mejora

### 1. Crear orden de reemplazo

Para productos defectuosos o incorrectos, un agente podria crear una orden de reemplazo si hay
stock disponible.

Tools adicionales:

- `check_replacement_stock`
- `create_replacement_order`

### 2. Actualizar informacion del cliente en CRM

El agente podria actualizar telefono, direccion o preferencias de contacto.

Control necesario:

- Validacion de identidad.
- Confirmacion explicita del usuario.
- Auditoria de cambios.

### 3. Clasificador semantico de intenciones

El router actual usa keywords. Una mejora seria usar embeddings o un clasificador supervisado para
detectar mejor solicitudes ambiguas.

### 4. Human-in-the-loop

Casos de alto riesgo deberian escalarse o transferirse a soporte humano dentro del mismo chat:

- Ordenes internacionales costosas.
- Reclamos repetidos.
- Productos perecederos sin evidencia clara.
- Solicitudes con lenguaje agresivo o sospecha de fraude.

Una mejora futura seria integrar una bandeja de agentes humanos o un conector de soporte para que
el usuario no tenga que cambiar de canal. El agente automatico podria marcar el estado
`manual_review`, mantener el contexto de la conversacion y permitir que un especialista humano
continúe desde el mismo chat, solicite la evidencia fotografica y autorice o rechace la devolucion.

### 5. Persistencia real de devoluciones

El prototipo genera etiquetas simuladas. En produccion se deberia integrar con:

- Sistema de ordenes.
- Sistema logistico.
- CRM.
- Motor de reembolsos.

Cada integracion deberia tener permisos minimos, logs y rollback.

### 6. Carga y validacion de evidencia fotografica

Una mejora directa seria permitir que el usuario cargue imagenes en Streamlit como evidencia de
daño, deterioro o producto incorrecto. Esa evidencia podria asociarse al RMA y pasar por una capa
de vision computacional.

Una posible arquitectura futura:

- `st.file_uploader` para recibir la imagen.
- Almacenamiento temporal o persistente de la evidencia.
- Modelo YOLO entrenado con imagenes de productos EcoMarket y ejemplos de daño.
- Validacion de confianza del modelo.
- Escalamiento a humano cuando la confianza sea baja o el caso sea ambiguo.

Hasta que esa capa exista, el prototipo evita aprobar automaticamente reclamos que dependan de
fotos.
