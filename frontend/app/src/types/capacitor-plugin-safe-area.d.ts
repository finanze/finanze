declare module "capacitor-plugin-safe-area" {
  export type SafeArea = {
    top: number
    right: number
    bottom: number
    left: number
  }

  export interface SafeAreaInsets {
    insets: SafeArea
  }

  export interface StatusBarInfo {
    statusBarHeight: number
  }

  export interface PluginListenerHandle {
    remove: () => Promise<void>
  }

  export const SafeArea: {
    getSafeAreaInsets: () => Promise<SafeAreaInsets>
    getStatusBarHeight: () => Promise<StatusBarInfo>
    addListener: (
      event: "safeAreaChanged",
      listenerFunc: (data: SafeAreaInsets) => void,
    ) => Promise<PluginListenerHandle>
    removeAllListeners: () => Promise<void>
    setImmersiveNavigationBar: (options?: {
      statusBarStyle?: "light" | "dark"
    }) => Promise<void>
    unsetImmersiveNavigationBar: (options?: {
      statusBarBg?: string
      statusBarStyle?: "light" | "dark"
    }) => Promise<void>
  }
}
