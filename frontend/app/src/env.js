// Access runtime variables injected by env-config.js from the global window object
const runtime = window.runtimeVariables || {}

export const BASE_URL = runtime.BASE_URL || import.meta.env.VITE_BASE_URL
