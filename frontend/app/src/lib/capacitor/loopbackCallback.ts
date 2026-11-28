import { registerPlugin } from "@capacitor/core"
import type { PluginListenerHandle } from "@capacitor/core"

export interface LoopbackCallbackStartOptions {
  path?: string
  timeoutMs?: number
}

export interface LoopbackCallbackPlugin {
  start(
    options?: LoopbackCallbackStartOptions,
  ): Promise<{ port: number; url: string }>
  stop(): Promise<void>

  addListener(
    eventName: "callback",
    handler: (data: { url: string }) => void,
  ): Promise<PluginListenerHandle>

  addListener(
    eventName: "timeout",
    handler: () => void,
  ): Promise<PluginListenerHandle>

  removeAllListeners(): Promise<void>
}

export const LoopbackCallback =
  registerPlugin<LoopbackCallbackPlugin>("LoopbackCallback")
