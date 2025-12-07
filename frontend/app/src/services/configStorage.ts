import type { FinanzeConfig } from "@/types"

const CONFIG_STORAGE_KEY = "backendConfig"

export const getConfig = (): FinanzeConfig => {
  try {
    const stored = localStorage.getItem(CONFIG_STORAGE_KEY)
    if (stored) {
      return JSON.parse(stored)
    }
  } catch (error) {
    console.error("Failed to load config from localStorage:", error)
  }
  return {}
}

export const saveConfig = (config: FinanzeConfig): void => {
  try {
    localStorage.setItem(CONFIG_STORAGE_KEY, JSON.stringify(config))
  } catch (error) {
    console.error("Failed to save config to localStorage:", error)
    throw error
  }
}

export const resetConfig = (): void => {
  try {
    localStorage.removeItem(CONFIG_STORAGE_KEY)
  } catch (error) {
    console.error("Failed to reset config in localStorage:", error)
    throw error
  }
}

export const hasConfig = (): boolean => {
  return localStorage.getItem(CONFIG_STORAGE_KEY) !== null
}
