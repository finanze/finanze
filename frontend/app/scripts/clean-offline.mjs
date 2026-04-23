import fs from "fs"
import path from "path"
import { fileURLToPath } from "url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const DIST_PYODIDE_DIR = path.resolve(__dirname, "../dist-pyodide")

function rmIfExists(p) {
  if (!fs.existsSync(p)) return
  fs.rmSync(p, { recursive: true, force: true })
}

console.log("[Offline] Cleaning cached offline assets...")
rmIfExists(DIST_PYODIDE_DIR)

console.log("[Offline] Clean complete.")
