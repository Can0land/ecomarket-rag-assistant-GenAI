const fs = require("fs");
const path = require("path");
const { spawnSync } = require("child_process");

const diagramDir = path.join("docs", "flujogramas");
const files = fs
  .readdirSync(diagramDir)
  .filter((file) => file.endsWith(".mmd"))
  .sort();

if (files.length === 0) {
  throw new Error(`No .mmd files found in ${diagramDir}`);
}

const formats = ["svg", "png"];

for (const file of files) {
  const input = path.join(diagramDir, file);
  const base = path.join(diagramDir, path.basename(file, ".mmd"));

  for (const format of formats) {
    const output = `${base}.${format}`;
    const result = spawnSync(
      "cmd.exe",
      [
        "/c",
        "npx",
        "-y",
        "@mermaid-js/mermaid-cli",
        "-i",
        input,
        "-o",
        output,
        "-b",
        "white",
        "-s",
        "2",
      ],
      {
        encoding: "utf8",
        stdio: "pipe",
      },
    );

    if (result.status !== 0) {
      if (result.error) {
        console.error(result.error);
      }
      console.error(result.stdout);
      console.error(result.stderr);
      throw new Error(`Failed to render ${input} as ${format}`);
    }

    console.log(`Rendered ${output}`);
  }
}
