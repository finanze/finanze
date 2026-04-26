import { registerPlugin } from "@capacitor/core"
import type { PluginListenerHandle } from "@capacitor/core"

export interface LoginWebViewOpenOptions {
  url: string
  title?: string
  clearSession?: boolean
  interceptUrlPatterns?: string[]
  injectScript?: string
}

export interface InterceptedRequest {
  url: string
  method: string
  headers: Record<string, string>
}

export interface InterceptedResponse {
  url: string
  statusCode: number
  headers: Record<string, string>
}

export interface LoginWebViewPlugin {
  open(options: LoginWebViewOpenOptions): Promise<void>
  close(): Promise<void>
  executeScript(options: { code: string }): Promise<{ result: string }>
  getCookies(options: {
    url: string
  }): Promise<{ cookies: Record<string, string>; raw: string }>
  clearData(): Promise<void>
  reload(): Promise<void>

  addListener(
    eventName: "requestIntercepted",
    handler: (data: InterceptedRequest) => void,
  ): Promise<PluginListenerHandle>

  addListener(
    eventName: "responseIntercepted",
    handler: (data: InterceptedResponse) => void,
  ): Promise<PluginListenerHandle>

  addListener(
    eventName: "closed",
    handler: () => void,
  ): Promise<PluginListenerHandle>

  addListener(
    eventName: "pageLoaded",
    handler: (data: { url: string }) => void,
  ): Promise<PluginListenerHandle>

  removeAllListeners(): Promise<void>
}

export const LoginWebView = __CONNECTIONS__
  ? registerPlugin<LoginWebViewPlugin>("LoginWebView")
  : (null as unknown as LoginWebViewPlugin)
