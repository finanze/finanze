import { isNativeMobile } from "@/lib/platform"
import { ApiServerInfo } from "./api"

export interface HelperOptions {
  headers?: Record<string, string>
  responseType?: "json" | "blob" | "text"
}

export interface ApiClient {
  getApiServerInfo(): Promise<ApiServerInfo>

  refreshApiBaseUrl(): Promise<void>

  get<T>(path: string, options?: HelperOptions): Promise<T>

  post<T>(path: string, body?: any, options?: HelperOptions): Promise<T>

  put<T>(path: string, body?: any, options?: HelperOptions): Promise<T>

  delete<T>(path: string, options?: HelperOptions): Promise<T>
  delete<T>(path: string, body?: any, options?: HelperOptions): Promise<T>

  download(
    path: string,
    body?: any,
  ): Promise<{
    blob: Blob
    filename: string | null
    contentType: string | null
  }>

  getImageUrl(path: string): Promise<string>
}

let apiClientInstance: ApiClient | null = null

export function setApiClient(client: ApiClient) {
  apiClientInstance = client
}

export async function getApiClient(): Promise<ApiClient> {
  if (!apiClientInstance) {
    if (__MOBILE__ && isNativeMobile()) {
      const module = await import("@/lib/pyodide/apiClient")
      apiClientInstance = new module.PyodideApiClient()
      console.log("Initialized Pyodide API client")
    } else {
      const module = await import("./httpApiClient")
      apiClientInstance = new module.HttpApiClient()
      console.log("Initialized HTTP API client")
    }
  }
  return apiClientInstance!
}
