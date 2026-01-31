import type { ApiServerInfo } from "../../services/api"
import type { ApiClient, HelperOptions } from "../../services/apiClient"
import { callPythonFunction } from "@/lib/pyodide"
import { appConsole } from "@/lib/capacitor/appConsole"
import { ensureInitialized, withApiPrefix } from "@/lib/pyodide/init"

function logInfo(message: string, data?: any) {
  appConsole.info(`[PyodideApiClient] ${message}`, data)
}

function logDebug(message: string, data?: any) {
  appConsole.debug(`[PyodideApiClient] ${message}`, data)
}

export class PyodideApiClient implements ApiClient {
  async getApiServerInfo(): Promise<ApiServerInfo> {
    return {
      isCustomServer: false,
      serverDisplay: null,
      baseUrl: "/",
    }
  }

  async refreshApiBaseUrl(): Promise<void> {}

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
    let fullPath = withApiPrefix(path)
    if (fullPath.endsWith("?")) {
      fullPath = fullPath.slice(0, -1)
    }

    const initMethod = body ? "POST" : "GET"
    await ensureInitialized(initMethod, fullPath)

    try {
      const response = await callPythonFunction<{
        status: number
        data: any
        headers: Record<string, string>
      }>("controller", "handle", body ? "POST" : "GET", fullPath, body, {})

      if (response.status >= 400) {
        const error: any = new Error(
          response.data?.message || "Download failed",
        )
        error.status = response.status
        throw error
      }

      // Convert response.data to Blob
      // Python bytes through Pyodide can come as:
      // - Uint8Array (ideal)
      // - ArrayBuffer
      // - Object with numeric keys like {0: 110, 1: 97, ...} (common case)
      // - String
      let blob: Blob
      if (response.data instanceof Uint8Array) {
        blob = new Blob([response.data as BlobPart])
      } else if (response.data instanceof ArrayBuffer) {
        blob = new Blob([response.data])
      } else if (typeof response.data === "string") {
        blob = new Blob([response.data], { type: "text/plain;charset=utf-8" })
      } else if (
        response.data &&
        typeof response.data === "object" &&
        "0" in response.data
      ) {
        // Pyodide converts Python bytes to an object with numeric keys {0: val, 1: val, ...}
        // Find the length by checking for the highest numeric key
        const keys = Object.keys(response.data)
          .filter(k => /^\d+$/.test(k))
          .map(Number)
        const maxIndex = Math.max(...keys)
        const uint8Array = new Uint8Array(maxIndex + 1)
        for (let i = 0; i <= maxIndex; i++) {
          uint8Array[i] = response.data[i] ?? 0
        }
        blob = new Blob([uint8Array as BlobPart])
      } else {
        // For other objects, stringify them
        blob = new Blob([JSON.stringify(response.data)], {
          type: "application/json",
        })
      }

      // Headers are in response.headers
      // Need to handle case-insensitivity if python returns specific case
      const headers = response.headers
      // Helper to get header case-insensitively
      const getHeader = (key: string) => {
        const k = key.toLowerCase()
        for (const h in headers) {
          if (h.toLowerCase() === k) return headers[h]
        }
        return null
      }

      const dispositionHeader = getHeader("Content-Disposition")
      let filename: string | null = null

      if (dispositionHeader) {
        // Same extraction logic
        const utfMatch = dispositionHeader.match(/filename\*=UTF-8''([^;]+)/i)
        if (utfMatch?.[1]) {
          try {
            filename = decodeURIComponent(utfMatch[1])
          } catch {
            filename = utfMatch[1]
          }
          filename = filename.replace(/^"|"$/g, "")
        } else {
          const fallbackMatch = dispositionHeader.match(
            /filename="?([^";]+)"?/i,
          )
          if (fallbackMatch?.[1]) {
            filename = fallbackMatch[1]
          }
        }
      }

      return {
        blob,
        filename,
        contentType: getHeader("Content-Type") || null,
      }
    } catch (e: any) {
      appConsole.error(`Pyodide Download Error [${path}]:`, e)
      throw new Error(typeof e === "string" ? e : e.message)
    }
  }

  async getImageUrl(path: string): Promise<string> {
    // For Pyodide, we must fetch the image data from Python and create a Blob URL
    // Assuming GET request to path returns image bytes
    const { blob } = await this.download(path)
    return URL.createObjectURL(blob)
  }

  private async request<T>(
    method: string,
    path: string,
    body?: any,
    options?: HelperOptions,
  ): Promise<T> {
    logInfo(`${method} ${path}`)
    logDebug(`Request body:`, body)
    logDebug(`Request options:`, options)

    let fullPath = withApiPrefix(path)
    if (fullPath.endsWith("?")) {
      fullPath = fullPath.slice(0, -1)
    }
    logDebug(`Full API path: ${fullPath}`)

    await ensureInitialized(method, fullPath)

    let payload = body
    if (body instanceof FormData) {
      const formDataPayload: Record<string, any> = {}
      for (const [key, value] of (body as any).entries()) {
        if (value instanceof Blob) {
          const buffer = await value.arrayBuffer()
          formDataPayload[key] = {
            _type: "file",
            name: (value as File).name || "blob",
            type: value.type,
            content: new Uint8Array(buffer),
          }
        } else {
          formDataPayload[key] = value
        }
      }
      payload = formDataPayload
    }

    const headers = options?.headers || {}

    try {
      logDebug(`${path} Body payload:`, payload)
      logDebug(`${path} Headers:`, headers)
      const response = await callPythonFunction<{
        status: number
        data: any
        headers: Record<string, string>
      }>("controller", "handle", method, fullPath, payload, headers)

      logDebug(`${path} Response status: ${response.status}`, response.data)

      if (response.status >= 400) {
        const error: any = new Error(response.data?.message || "Request failed")
        error.status = response.status
        error.code = response.data?.code
        error.details = response.data?.details
        throw error
      }

      if (response.status === 204) {
        return null as unknown as T
      }

      return response.data as T
    } catch (e: any) {
      appConsole.error(`[PyodideApiClient] ${method} ${path}:`, e)

      if (typeof e === "string") {
        throw new Error(e)
      }
      throw e
    }
  }
}
