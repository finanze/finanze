export enum OS {
  MAC = "mac",
  WINDOWS = "windows",
  LINUX = "linux",
}

export interface AppConfig {
  readonly isDev: boolean
  readonly os: OS
  readonly ports: {
    backend: number
  }
  readonly urls: {
    backend: string
    vite: string
  }
}
