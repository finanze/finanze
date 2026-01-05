import { createClient } from "@supabase/supabase-js"
import * as SecureStore from "expo-secure-store"
import { Config } from "../../config"

const CHUNK_COUNT_SUFFIX = ".__chunks"
const CHUNK_SUFFIX_PREFIX = ".__chunk_"
// Expo SecureStore has a ~2KB per-item limit; keep a buffer for metadata.
const MAX_CHUNK_SIZE = 1800

const removeChunks = async (key: string) => {
  const countRaw = await SecureStore.getItemAsync(`${key}${CHUNK_COUNT_SUFFIX}`)
  const count = countRaw ? Number(countRaw) : 0
  if (Number.isFinite(count) && count > 0) {
    for (let i = 0; i < count; i++) {
      await SecureStore.deleteItemAsync(`${key}${CHUNK_SUFFIX_PREFIX}${i}`)
    }
  }
  await SecureStore.deleteItemAsync(`${key}${CHUNK_COUNT_SUFFIX}`)
}

// Custom storage adapter using expo-secure-store for secure token storage
const ExpoSecureStoreAdapter = {
  getItem: async (key: string): Promise<string | null> => {
    try {
      const direct = await SecureStore.getItemAsync(key)
      if (direct) return direct

      const countRaw = await SecureStore.getItemAsync(
        `${key}${CHUNK_COUNT_SUFFIX}`,
      )
      if (!countRaw) return null
      const count = Number(countRaw)
      if (!Number.isFinite(count) || count <= 0) return null

      const parts: string[] = []
      for (let i = 0; i < count; i++) {
        const part = await SecureStore.getItemAsync(
          `${key}${CHUNK_SUFFIX_PREFIX}${i}`,
        )
        if (part == null) return null
        parts.push(part)
      }
      return parts.join("")
    } catch (error) {
      console.error("SecureStore getItem error:", error)
      return null
    }
  },
  setItem: async (key: string, value: string): Promise<void> => {
    try {
      if (value.length <= MAX_CHUNK_SIZE) {
        await SecureStore.setItemAsync(key, value)
        await removeChunks(key)
        return
      }

      // Store chunked; keep the main key empty to avoid warnings.
      await SecureStore.deleteItemAsync(key)
      await removeChunks(key)

      const chunks: string[] = []
      for (let i = 0; i < value.length; i += MAX_CHUNK_SIZE) {
        chunks.push(value.slice(i, i + MAX_CHUNK_SIZE))
      }

      await SecureStore.setItemAsync(
        `${key}${CHUNK_COUNT_SUFFIX}`,
        String(chunks.length),
      )
      for (let i = 0; i < chunks.length; i++) {
        await SecureStore.setItemAsync(
          `${key}${CHUNK_SUFFIX_PREFIX}${i}`,
          chunks[i],
        )
      }
    } catch (error) {
      console.error("SecureStore setItem error:", error)
    }
  },
  removeItem: async (key: string): Promise<void> => {
    try {
      await SecureStore.deleteItemAsync(key)
      await removeChunks(key)
    } catch (error) {
      console.error("SecureStore removeItem error:", error)
    }
  },
}

export const supabase = createClient(
  Config.SUPABASE_URL!,
  Config.SUPABASE_ANON_KEY!,
  {
    auth: {
      storage: ExpoSecureStoreAdapter,
      flowType: "pkce",
      autoRefreshToken: true,
      persistSession: true,
      detectSessionInUrl: false,
    },
  },
)

export default supabase
