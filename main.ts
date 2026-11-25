import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __filename: string = fileURLToPath(import.meta.url);
const __dirname: string = path.dirname(__filename);

const SOURCE_IMAGE: string = path.join(__dirname, "assets", "entry.png");
const OUTPUT_DIR: string = "/output";
const OUTPUT_IMAGE: string = path.join(OUTPUT_DIR, "entry.png");

fs.mkdirSync(OUTPUT_DIR, { recursive: true });
fs.copyFileSync(SOURCE_IMAGE, OUTPUT_IMAGE);
