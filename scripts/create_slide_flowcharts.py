from __future__ import annotations

from html import escape
from pathlib import Path
from textwrap import wrap


OUT_DIR = Path("docs/flujogramas_diapositivas")
WIDTH = 1920
HEIGHT = 1080

COLORS = {
    "user": ("#EEF6FF", "#2F80ED"),
    "app": ("#EFFAF1", "#27AE60"),
    "logic": ("#F4ECFF", "#8E44AD"),
    "data": ("#EAF8FB", "#22A6B3"),
    "llm": ("#FFF3E8", "#F2994A"),
    "agent": ("#FCEAF1", "#EB5757"),
    "direct": ("#FFF9E6", "#F2C94C"),
}

SLIDES = [
    {
        "file": "01_inicio_app_slide_16_9.svg",
        "title": "Inicio de la aplicacion",
        "steps": [
            ("Usuario abre EcoMarket", "user"),
            ("Streamlit inicia app.py", "app"),
            ("Carga o crea FAISS", "data"),
            ("Lee politicas, catalogo, inventario y ordenes", "data"),
            ("Inicializa session_state", "app"),
            ("Espera el mensaje del usuario", "user"),
        ],
    },
    {
        "file": "02_mensaje_respuesta_slide_16_9.svg",
        "title": "Del mensaje a la respuesta",
        "steps": [
            ("Usuario escribe en el chat", "user"),
            ("app.py guarda y muestra el mensaje", "app"),
            ("chat_handler.py procesa la entrada", "app"),
            ("router.py detecta la intencion", "logic"),
            ("Se elige el flujo correcto", "logic"),
            ("Consulta datos, RAG, agente o respuesta directa", "data"),
            ("Gemma genera o mejora la respuesta", "llm"),
            ("Streamlit muestra el resultado", "app"),
        ],
    },
    {
        "file": "03_tipos_respuesta_slide_16_9.svg",
        "title": "Tipos de respuesta del asistente",
        "steps": [
            ("Router de intenciones", "logic"),
            ("Respuesta directa: saludo, abuso, limites o datos faltantes", "direct"),
            ("Datos estructurados: ordenes e inventario", "data"),
            ("RAG + LLM: politicas y catalogo", "llm"),
            ("Agente de devoluciones: tools y registro", "agent"),
        ],
    },
    {
        "file": "04_agente_devoluciones_slide_16_9.svg",
        "title": "Agente de devoluciones",
        "steps": [
            ("Usuario solicita devolucion", "user"),
            ("Busca orden y producto", "data"),
            ("Verifica si faltan datos", "logic"),
            ("Tool valida reglas de politica", "agent"),
            ("Si aprueba, genera etiqueta RMA", "agent"),
            ("Si no aprueba, pide datos, escala o rechaza", "direct"),
            ("Registra la accion y muestra el SVG", "app"),
        ],
    },
    {
        "file": "05_renderizado_final_slide_16_9.svg",
        "title": "Renderizado de la respuesta final",
        "steps": [
            ("Respuesta lista", "llm"),
            ("Actualiza session_state", "app"),
            ("Guarda historial, fuentes y estado RAG", "data"),
            ("Detecta si hay etiqueta SVG", "logic"),
            ("Renderiza markdown normal o separa texto + SVG", "app"),
            ("Refresca la interfaz", "user"),
        ],
    },
]


def line_icon(kind: str, x: int, y: int, stroke: str) -> str:
    if kind == "user":
        return (
            f'<circle cx="{x}" cy="{y - 13}" r="18" fill="{stroke}" opacity=".9"/>'
            f'<path d="M{x - 36} {y + 42} Q{x} {y + 2} {x + 36} {y + 42}" '
            f'fill="{stroke}" opacity=".9"/>'
        )
    if kind == "data":
        return (
            f'<ellipse cx="{x}" cy="{y - 28}" rx="34" ry="12" fill="none" stroke="{stroke}" stroke-width="7"/>'
            f'<path d="M{x - 34} {y - 28} V{y + 30} C{x - 34} {y + 46} {x + 34} {y + 46} {x + 34} {y + 30} V{y - 28}" '
            f'fill="none" stroke="{stroke}" stroke-width="7"/>'
        )
    if kind == "logic":
        return (
            f'<path d="M{x} {y - 48} L{x + 48} {y} L{x} {y + 48} L{x - 48} {y} Z" '
            f'fill="none" stroke="{stroke}" stroke-width="7" stroke-linejoin="round"/>'
        )
    if kind == "llm":
        return (
            f'<circle cx="{x}" cy="{y}" r="43" fill="none" stroke="{stroke}" stroke-width="7"/>'
            f'<path d="M{x - 18} {y - 20} V{y + 20} M{x + 18} {y - 20} V{y + 20} '
            f'M{x - 36} {y} H{x + 36}" stroke="{stroke}" stroke-width="7" stroke-linecap="round"/>'
        )
    if kind == "agent":
        return (
            f'<path d="M{x - 42} {y + 22} H{x + 42} M{x - 28} {y + 22} V{y - 10} '
            f'M{x} {y + 22} V{y - 34} M{x + 28} {y + 22} V{y - 10}" '
            f'stroke="{stroke}" stroke-width="7" stroke-linecap="round"/>'
            f'<circle cx="{x}" cy="{y - 48}" r="12" fill="{stroke}"/>'
        )
    if kind == "direct":
        return (
            f'<path d="M{x - 40} {y - 36} H{x + 40} V{y + 18} H{x - 4} L{x - 34} {y + 42} '
            f'V{y + 18} H{x - 40} Z" fill="none" stroke="{stroke}" stroke-width="7" stroke-linejoin="round"/>'
        )
    return f'<rect x="{x - 40}" y="{y - 40}" width="80" height="80" fill="none" stroke="{stroke}" stroke-width="7"/>'


def text_lines(text: str, max_chars: int) -> list[str]:
    return wrap(text, width=max_chars, break_long_words=False)


def draw_node(label: str, kind: str, x: int, y: int, w: int, h: int) -> str:
    fill, stroke = COLORS[kind]
    icon_x = x + 68
    icon_y = y + h // 2
    text_x = x + 132
    font_size = 28 if w <= 410 else 30
    line_height = 36
    usable_width = w - 165
    max_chars = max(13, int(usable_width / (font_size * 0.58)))
    lines = text_lines(label, max_chars)
    first_y = y + h // 2 - (len(lines) - 1) * (line_height // 2) + 10
    text = "".join(
        f'<text x="{text_x}" y="{first_y + i * line_height}" font-size="{font_size}" '
        f'font-family="Arial, sans-serif" fill="#111827">{escape(line)}</text>'
        for i, line in enumerate(lines)
    )
    return (
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="22" fill="{fill}" '
        f'stroke="{stroke}" stroke-width="4"/>'
        f'{line_icon(kind, icon_x, icon_y, stroke)}{text}'
    )


def arrow(x1: int, y1: int, x2: int, y2: int) -> str:
    return (
        f'<path d="M{x1} {y1} L{x2} {y2}" stroke="#111827" stroke-width="7" '
        f'stroke-linecap="round" marker-end="url(#arrow)"/>'
    )


def layout_positions(count: int) -> tuple[list[tuple[int, int, int, int]], list[tuple[int, int, int, int]]]:
    if count <= 6:
        w, h = 520, 180
        rows = [3, count - 3]
    elif count == 7:
        w, h = 430, 180
        rows = [4, 3]
    else:
        w, h = 430, 180
        rows = [4, 4]

    positions = []
    y_values = [230, 650]
    for row_index, row_count in enumerate(rows):
        total = row_count * w + (row_count - 1) * 55
        start_x = (WIDTH - total) // 2
        for i in range(row_count):
            positions.append((start_x + i * (w + 55), y_values[row_index], w, h))

    arrows = []
    for i in range(count - 1):
        x, y, w0, h0 = positions[i]
        nx, ny, nw, nh = positions[i + 1]
        if ny == y:
            arrows.append((x + w0 + 10, y + h0 // 2, nx - 10, ny + nh // 2))
        else:
            arrows.append((x + w0 // 2, y + h0 + 14, nx + nw // 2, ny - 14))
    return positions, arrows


def render_slide(slide: dict[str, object]) -> str:
    steps = slide["steps"]
    positions, arrows = layout_positions(len(steps))
    nodes = "".join(draw_node(label, kind, *positions[i]) for i, (label, kind) in enumerate(steps))
    connectors = "".join(arrow(*coords) for coords in arrows)
    title = escape(str(slide["title"]))
    return f'''<svg xmlns="http://www.w3.org/2000/svg" width="{WIDTH}" height="{HEIGHT}" viewBox="0 0 {WIDTH} {HEIGHT}">
  <defs>
    <marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="9" markerHeight="9" orient="auto-start-reverse">
      <path d="M 0 0 L 10 5 L 0 10 z" fill="#111827"/>
    </marker>
    <filter id="softShadow" x="-10%" y="-10%" width="120%" height="120%">
      <feDropShadow dx="0" dy="8" stdDeviation="8" flood-color="#000000" flood-opacity="0.10"/>
    </filter>
  </defs>
  <rect width="{WIDTH}" height="{HEIGHT}" fill="#FFFFFF"/>
  <text x="960" y="115" text-anchor="middle" font-size="58" font-weight="700" font-family="Arial, sans-serif" fill="#111827">{title}</text>
  <g filter="url(#softShadow)">
    {connectors}
    {nodes}
  </g>
</svg>
'''


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for slide in SLIDES:
        (OUT_DIR / str(slide["file"])).write_text(render_slide(slide), encoding="utf-8")


if __name__ == "__main__":
    main()
