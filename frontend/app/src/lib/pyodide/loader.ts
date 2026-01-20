import { appConsole } from "../capacitor/appConsole"
import { getPyodide } from "./runtime"

const MANIFEST_PATH = "/python/manifest.json"
const PYTHON_ROOT = "/python"

interface Manifest {
  files: string[]
}

export async function loadAppModules(): Promise<void> {
  appConsole.info("[Pyodide] Loading app modules...")
  const pyodide = getPyodide()

  const response = await fetch(MANIFEST_PATH)
  if (!response.ok) {
    throw new Error(`Failed to load manifest: ${response.statusText}`)
  }
  const manifest: Manifest = await response.json()

  const errors: string[] = []

  await Promise.all(
    manifest.files.map(async filePath => {
      try {
        const fileRes = await fetch(`${PYTHON_ROOT}/${filePath}`)
        if (!fileRes.ok) throw new Error(fileRes.statusText)

        const content = await fileRes.arrayBuffer()
        const data = new Uint8Array(content)

        const targetPath = `${PYTHON_ROOT}/${filePath}`

        // Ensure directory exists
        const dir = targetPath.substring(0, targetPath.lastIndexOf("/"))
        if (dir) {
          pyodide.FS.mkdirTree(dir)
        }

        pyodide.FS.writeFile(targetPath, data)
      } catch (e) {
        appConsole.error(`Failed to load ${filePath}:`, e)
        errors.push(filePath)
      }
    }),
  )

  if (errors.length > 0) {
    appConsole.warn(`[Pyodide] Failed to load ${errors.length} files.`)
  } else {
    appConsole.info(`[Pyodide] Loaded ${manifest.files.length} modules.`)
  }

  // Add /python to sys.path so 'import finanze' works
  await pyodide.runPythonAsync(`
import sys
import os
if "/python" not in sys.path:
    sys.path.insert(0, "/python")
if "/python/finanze" not in sys.path:
    sys.path.insert(0, "/python/finanze")
print(f"Current working directory: {os.getcwd()}")
print(f"sys.path: {sys.path}")
`)
}
