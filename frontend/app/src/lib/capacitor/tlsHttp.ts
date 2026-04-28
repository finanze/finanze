import { registerPlugin } from "@capacitor/core"

export interface TlsHttpRequestOptions {
  url: string
  method: string
  headers?: Record<string, string>
  data?: string
  responseType?: string
  sessionId?: string
}

export interface TlsHttpResponse {
  status: number
  headers: Record<string, string>
  data: string
}

export interface TlsHttpPlugin {
  request(options: TlsHttpRequestOptions): Promise<TlsHttpResponse>
  destroySession(options: { sessionId: string }): Promise<void>
}

export const TlsHttp = __CONNECTIONS__
  ? registerPlugin<TlsHttpPlugin>("TlsHttp")
  : (null as unknown as TlsHttpPlugin)
