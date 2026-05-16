const fs = require("fs");
const path = require("path");

const inputPath = path.join("docs", "flujograma_flujo_trabajo_asistente.md");
const outputDir = path.join("docs", "flujogramas");

const names = [
  "01_inicializacion_aplicacion",
  "02_flujo_principal_mensaje_respuesta",
  "03_ramas_tipo_respuesta",
  "04_subflujo_agente_devoluciones",
  "05_renderizado_respuesta_final",
];

const content = fs.readFileSync(inputPath, "utf8");
const blocks = [...content.matchAll(/```mermaid\r?\n([\s\S]*?)```/g)].map(
  (match) => match[1].trim() + "\n",
);

if (blocks.length === 0) {
  throw new Error(`No Mermaid blocks found in ${inputPath}`);
}

fs.mkdirSync(outputDir, { recursive: true });

blocks.forEach((block, index) => {
  const name = names[index] || `${String(index + 1).padStart(2, "0")}_diagrama`;
  fs.writeFileSync(path.join(outputDir, `${name}.mmd`), block, "utf8");
});

console.log(`Extracted ${blocks.length} Mermaid diagrams to ${outputDir}`);
