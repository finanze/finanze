import { isNativeMobile } from "@/lib/platform"
import { ApiServerInfo } from "./api"
import { HttpApiClient } from "./httpApiClient"
import { PyodideApiClient } from "./pyodideApiClient"

export interface HelperOptions {
  headers?: Record<string, string>
  responseType?: "json" | "blob" | "text"
}

export interface ApiClient {
  getApiServerInfo(): Promise<ApiServerInfo>

  refreshApiBaseUrl(): Promise<void>

  /**
   * Perform a GET request.
   */
  get<T>(path: string, options?: HelperOptions): Promise<T>

  /**
   * Perform a POST request.
   */
  post<T>(path: string, body?: any, options?: HelperOptions): Promise<T>

  /**
   * Perform a PUT request.
   */
  put<T>(path: string, body?: any, options?: HelperOptions): Promise<T>

  /**
   * Perform a DELETE request.
   */
  delete<T>(path: string, options?: HelperOptions): Promise<T>
  delete<T>(path: string, body?: any, options?: HelperOptions): Promise<T>

  /**
   * Perform a download request.
   */
  download(
    path: string,
    body?: any,
  ): Promise<{
    blob: Blob
    filename: string | null
    contentType: string | null
  }>

  /**
   * Get a URL for an image (resolves to absolute URL or Blob URL).
   */
  getImageUrl(path: string): Promise<string>
}

let apiClientInstance: ApiClient | null = null

export function setApiClient(client: ApiClient) {
  apiClientInstance = client
}

export function getApiClient(): ApiClient {
  if (!apiClientInstance) {
    if (isNativeMobile()) {
      apiClientInstance = new PyodideApiClient()
      console.log("Initialized Pyodide API client")
    } else {
      apiClientInstance = new HttpApiClient()
      console.log("Initialized HTTP API client")
    }
  }
  return apiClientInstance!
}
