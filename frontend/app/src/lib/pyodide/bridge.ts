import { sqliteBridge } from "./bridges/sqliteBridge"
import { preferencesBridge } from "./bridges/preferencesBridge"
import { registerJsFunctions, isPyodideReady } from "./runtime"
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

  registerJsFunctions({
    // SQLite functions
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_sqlite_open: jsBridge.sqlite.openDatabase,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_sqlite_execute: jsBridge.sqlite.executeSql,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_sqlite_query: jsBridge.sqlite.querySql,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_sqlite_transaction: jsBridge.sqlite.executeTransaction,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_sqlite_batch: jsBridge.sqlite.executeBatch,
    js_sqlite_close: jsBridge.sqlite.closeDatabase,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_sqlite_set_key: jsBridge.sqlite.setEncryptionKey,

    // Preferences functions
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_preferences_get: jsBridge.preferences.get,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_preferences_set: jsBridge.preferences.set,
    // @ts-expect-error Type mismatch with Pyodide function signature
    js_preferences_remove: jsBridge.preferences.remove,
    js_preferences_clear: jsBridge.preferences.clear,
  })

  // Expose bridge globally so 'import js' -> js.jsBridge works
  // @ts-expect-error Dynamic global assignment
  globalThis.jsBridge = jsBridge

  appConsole.debug("[Bridge] JS bridge registered with Pyodide")
}
