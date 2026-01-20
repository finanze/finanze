import type { ApiServerInfo } from "./api"
import type { ApiClient, HelperOptions } from "./apiClient"
import { BASE_URL } from "@/env"

let apiBaseUrl = BASE_URL
let apiUrlInitPromise: Promise<void> | null = null
let isCustomServer = false
let customServerUrl: string | null = null
let apiUrlInitialized = false

const withApiVersionSegment = (url: string): string => {
  let normalized = url.trim()
  if (!normalized) {
    throw new Error("Invalid base URL")
  }
  while (normalized.endsWith("/")) {
    normalized = normalized.slice(0, -1)
  }
  if (!normalized.endsWith("/api/v1")) {
    normalized = `${normalized}/api/v1`
  }
  return normalized
}

const initializeApiUrl = async (): Promise<void> => {
  try {
    if (
      typeof window !== "undefined" &&
      window.ipcAPI &&
      window.ipcAPI.apiUrl
    ) {
      const result = await window.ipcAPI.apiUrl()
      if (result?.url) {
        apiBaseUrl = result.url
        isCustomServer = result.custom
        if (isCustomServer) {
          customServerUrl = result.url
        }
        console.log("API URL initialized from IPC:", apiBaseUrl)
      }
    }
  } catch (error) {
    console.error("Error initializing API URL:", error)
  } finally {
    apiBaseUrl = withApiVersionSegment(apiBaseUrl)
    apiUrlInitialized = true
  }
}

const ensureInitPromise = (): Promise<void> => {
  if (!apiUrlInitPromise) {
    apiUrlInitPromise = initializeApiUrl()
  }
  return apiUrlInitPromise
}

const ensureApiUrlInitialized = async (): Promise<string> => {
  if (!apiUrlInitialized) {
    await ensureInitPromise()
  }
  return apiBaseUrl
}

export class HttpApiClient implements ApiClient {
  async getApiServerInfo(): Promise<ApiServerInfo> {
    await ensureInitPromise()
    return {
      isCustomServer,
      serverDisplay: customServerUrl,
      baseUrl: apiBaseUrl.replace(/\/api\/v1$/, ""),
    }
  }

  async refreshApiBaseUrl(): Promise<void> {
    apiBaseUrl = BASE_URL
    apiUrlInitialized = false
    apiUrlInitPromise = null
    isCustomServer = false
    customServerUrl = null
    await ensureApiUrlInitialized()
  }

  async get<T>(path: string, options?: HelperOptions): Promise<T> {
    return this.request("GET", path, undefined, options)
  }

  async post<T>(path: string, body?: any, options?: HelperOptions): Promise<T> {
    return this.request("POST", path, body, options)
  }

  async put<T>(path: string, body?: any, options?: HelperOptions): Promise<T> {
    return this.request("PUT", path, body, options)
  }

  async delete<T>(
    path: string,
    bodyOrOptions?: any,
    options?: HelperOptions,
  ): Promise<T> {
    let body = undefined
    let opts = options

    if (bodyOrOptions && !options && !this.isHelperOptions(bodyOrOptions)) {
      // Assume second arg is body if it doesn't look like options or if options is undefined
      // Actually, if signature is (path, options) vs (path, body, options)
      // Overloading implementation:
      body = bodyOrOptions
    } else if (bodyOrOptions && this.isHelperOptions(bodyOrOptions)) {
      opts = bodyOrOptions
      body = undefined
    } else if (bodyOrOptions && options) {
      body = bodyOrOptions
      opts = options
    }

    return this.request("DELETE", path, body, opts)
  }

  private isHelperOptions(obj: any): obj is HelperOptions {
    return (
      obj &&
      (typeof obj.headers === "object" || typeof obj.responseType === "string")
    )
  }

  async download(
    path: string,
    body?: any,
  ): Promise<{
    blob: Blob
    filename: string | null
    contentType: string | null
  }> {
    const baseUrl = await ensureApiUrlInitialized()
    const url = `${baseUrl}${path}`
    const options: RequestInit = {
      method: body ? "POST" : "GET",
      headers: body ? { "Content-Type": "application/json" } : {},
      body: body ? JSON.stringify(body) : undefined,
    }

    const response = await fetch(url, options)

    if (!response.ok) {
      // Reuse internal error handling logic if possible, or replicate it
      // Since we need to throw specific error format
      const data = await response.json().catch(() => ({}))
      const error: any = new Error(data.message || "Download failed")
      error.status = response.status
      error.code = data.code
      error.details = data.details
      error.data = data
      throw error
    }

    const blob = await response.blob()
    const dispositionHeader =
      response.headers.get("Content-Disposition") ||
      response.headers.get("content-disposition")
    let filename: string | null = null

    // Extract filename logic from api.ts
    if (dispositionHeader) {
      const utfMatch = dispositionHeader.match(/filename\*=UTF-8''([^;]+)/i)
      if (utfMatch?.[1]) {
        try {
          filename = decodeURIComponent(utfMatch[1])
        } catch {
          filename = utfMatch[1]
        }
        filename = filename.replace(/^"|"$/g, "")
      } else {
        const fallbackMatch = dispositionHeader.match(/filename="?([^";]+)"?/i)
        if (fallbackMatch?.[1]) {
          filename = fallbackMatch[1]
        }
      }
    }

    return {
      blob,
      filename,
      contentType:
        response.headers.get("Content-Type") ||
        response.headers.get("content-type"),
    }
  }

  async getImageUrl(path: string): Promise<string> {
    const baseUrl = await ensureApiUrlInitialized()
    // Remove /api/v1 from the end and add the image path if necessary, but baseUrl usually includes /api/v1
    // api.ts logic: const imageBaseUrl = baseUrl.replace("/api/v1", "")
    const imageBaseUrl = baseUrl.replace("/api/v1", "")
    return `${imageBaseUrl}${path}`
  }

  private async request<T>(
    method: string,
    path: string,
    body?: any,
    options?: HelperOptions,
  ): Promise<T> {
    const baseUrl = await ensureApiUrlInitialized()
    const url = `${baseUrl}${path}`

    const headers: Record<string, string> = {
      ...options?.headers,
    }

    let requestBody: any = undefined
    if (body) {
      if (body instanceof FormData) {
        requestBody = body
      } else {
        if (!headers["Content-Type"]) {
          headers["Content-Type"] = "application/json"
        }
        requestBody = JSON.stringify(body)
      }
    }

    const config: RequestInit = {
      method,
      headers,
      body: requestBody,
    }

    const response = await fetch(url, config)

    // Handle Blob/Text responses
    if (options?.responseType === "blob") {
      if (!response.ok) this.handleError(response)
      return (await response.blob()) as unknown as T
    }

    if (options?.responseType === "text") {
      if (!response.ok) this.handleError(response)
      return (await response.text()) as unknown as T
    }

    let data
    try {
      if (response.status !== 204) {
        data = await response.json()
      }
    } catch {
      if (!response.ok) {
        this.handleError(response)
      }
      throw new Error("Failed to parse JSON response")
    }

    if (!response.ok) {
      // Replicating api.ts error structure if possible
      // api.ts throws the data directly or wrapped
      // We'll throw an object attached with status
      const error: any = new Error(data.message || "Request failed")
      error.status = response.status
      error.code = data.code
      error.details = data.details
      error.data = data
      throw error
    }

    return data
  }

  private handleError(response: Response) {
    const error: any = new Error(response.statusText)
    error.status = response.status
    throw error
  }
}
