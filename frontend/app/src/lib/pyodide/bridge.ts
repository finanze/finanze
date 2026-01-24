import { sqliteBridge } from "./bridges/sqliteBridge"
import { preferencesBridge } from "./bridges/preferencesBridge"
import { isPyodideReady } from "./runtime"
import { appConsole } from "../capacitor/appConsole"

export const jsBridge = {
  sqlite: {
    ...sqliteBridge,
  },
  preferences: {
    ...preferencesBridge,
  },
}

export function registerBridgeWithPyodide(): void {
  if (!isPyodideReady()) {
    throw new Error("Pyodide not initialized. Call initPyodide() first.")
  }

  // Expose bridge globally so 'import js' -> js.jsBridge works
  // @ts-expect-error Dynamic global assignment
  globalThis.jsBridge = jsBridge

  appConsole.debug("[Bridge] JS bridge registered with Pyodide")
}
