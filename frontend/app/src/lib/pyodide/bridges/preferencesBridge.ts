import { Preferences } from "@capacitor/preferences"

async function preferencesGet(key: string): Promise<string | null> {
  const result = await Preferences.get({ key })
  return result.value
}

async function preferencesSet(key: string, value: string): Promise<void> {
  await Preferences.set({ key, value })
}

async function preferencesRemove(key: string): Promise<void> {
  await Preferences.remove({ key })
}

async function preferencesClear(): Promise<void> {
  await Preferences.clear()
}

export const preferencesBridge = {
  get: preferencesGet,
  set: preferencesSet,
  remove: preferencesRemove,
  clear: preferencesClear,
}
