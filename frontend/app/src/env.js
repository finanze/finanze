// Access runtime variables injected by env-config.js from the global window object
const runtime = window.runtimeVariables || {}

export const BASE_URL = runtime.BASE_URL || import.meta.env.VITE_BASE_URL

export const BS_FRONTEND_TOKEN =
  runtime.BS_FRONTEND_TOKEN || import.meta.env.VITE_BS_FRONTEND_TOKEN || ""

export const BS_MOBILE_BACKEND_DSN =
  runtime.BS_MOBILE_BACKEND_DSN ||
  import.meta.env.VITE_BS_MOBILE_BACKEND_DSN ||
  ""

export const BS_ENVIRONMENT =
  runtime.BS_ENVIRONMENT ||
  import.meta.env.VITE_BS_ENVIRONMENT ||
  (import.meta.env.DEV ? "development" : "production")
