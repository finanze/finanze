import AsyncStorage from "@react-native-async-storage/async-storage"
import { Buffer } from "buffer"
import { Backupable, ConfigStoragePort } from "@/application/ports"
import { SettingsMetadata } from "@/domain/settings"

const CONFIG_PAYLOAD_KEY = "finanze.config.v1.payload_base64"

const stripQuotes = (value: string) => value.replace(/^['"]|['"]$/g, "")

const parseIsoDate = (value: string | null): Date | null => {
  if (!value) return null
  const d = new Date(value)
  return Number.isFinite(d.getTime()) ? d : null
}

const parseSettingsMetadata = (raw: string): SettingsMetadata => {
  const text = raw.trim()
  if (!text) {
    return { lastUpdate: null, defaultCurrency: null }
  }

  // Try JSON first (some clients may serialize config as JSON).
  try {
    const obj = JSON.parse(text) as any
    const lastUpdate =
      typeof obj?.lastUpdate === "string" ? parseIsoDate(obj.lastUpdate) : null
    const defaultCurrency =
      typeof obj?.general?.defaultCurrency === "string"
        ? obj.general.defaultCurrency
        : null

    return {
      lastUpdate,
      defaultCurrency,
    }
  } catch {
    // Fall back to YAML-ish parsing.
  }

  let lastUpdateStr: string | null = null
  let defaultCurrencyStr: string | null = null

  let inGeneral = false
  let generalIndent: number | null = null

  const lines = text.split(/\r?\n/)
  for (const line of lines) {
    const withoutComment = line.split("#")[0]
    if (!withoutComment.trim()) continue

    const indent = withoutComment.match(/^\s*/)?.[0]?.length ?? 0
    const trimmed = withoutComment.trim()

    if (trimmed.startsWith("lastUpdate:")) {
      lastUpdateStr = stripQuotes(trimmed.slice("lastUpdate:".length).trim())
      continue
    }

    if (trimmed === "general:") {
      inGeneral = true
      generalIndent = indent
      continue
    }

    if (inGeneral) {
      if (generalIndent != null && indent <= generalIndent) {
        inGeneral = false
        generalIndent = null
        // Continue parsing this line outside general.
      } else if (trimmed.startsWith("defaultCurrency:")) {
        defaultCurrencyStr = stripQuotes(
          trimmed.slice("defaultCurrency:".length).trim(),
        )
      }
    }
  }

  return {
    lastUpdate: parseIsoDate(lastUpdateStr),
    defaultCurrency: defaultCurrencyStr,
  }
}

const parseSettingsMetadataFromBytes = (
  bytes: Uint8Array,
): SettingsMetadata => {
  const text = new TextDecoder("utf-8").decode(bytes)
  return parseSettingsMetadata(text)
}

export class AsyncStorageConfigStorage
  implements ConfigStoragePort, Backupable
{
  async saveConfig(data: Uint8Array, lastUpdated?: Date): Promise<void> {
    const payloadBase64 = Buffer.from(data).toString("base64")

    await AsyncStorage.setItem(CONFIG_PAYLOAD_KEY, payloadBase64)
  }

  async getConfig(): Promise<Uint8Array | null> {
    const payloadBase64 = await AsyncStorage.getItem(CONFIG_PAYLOAD_KEY)
    if (!payloadBase64) return null

    const buf = Buffer.from(payloadBase64, "base64")
    return new Uint8Array(buf)
  }

  async getLastUpdated(): Promise<Date> {
    const payload = await this.getConfig()
    if (!payload) return new Date(0)

    const meta = parseSettingsMetadataFromBytes(payload)
    return meta.lastUpdate ?? new Date(0)
  }

  async getDefaultCurrency(): Promise<string | null> {
    const payload = await this.getConfig()
    if (!payload) return null

    const meta = parseSettingsMetadataFromBytes(payload)
    const currency = meta.defaultCurrency?.trim() ?? null
    return currency && currency.length > 0 ? currency : null
  }

  async clearConfig(): Promise<void> {
    await AsyncStorage.removeItem(CONFIG_PAYLOAD_KEY)
  }

  async importData(data: Uint8Array, importedAt?: Date): Promise<void> {
    await this.saveConfig(data)
  }
}
