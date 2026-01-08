import pako from "pako"
import { Buffer } from "buffer"

import { PBKDF2_ITERATIONS } from "./constants"
import type { DeriveKeyResult, FernetDecryptResult } from "./types"
import { deriveKeyJs, fernetDecryptJs } from "./jsImpl"

type DerivedKeyCache = { password: string; key: Buffer } | null

function nowMs(): number {
  return (globalThis as any)?.performance?.now?.() ?? Date.now()
}

export class BackupCryptoService {
  private derivedKeyCache: DerivedKeyCache = null

  async deriveKey(password: string): Promise<DeriveKeyResult> {
    if (this.derivedKeyCache?.password === password) {
      return {
        key: this.derivedKeyCache.key,
        meta: {
          cacheHit: true,
          ms: 0,
          iterations: PBKDF2_ITERATIONS,
          native: false,
        },
      }
    }

    const start = nowMs()
    const key = deriveKeyJs(password)
    const end = nowMs()

    this.derivedKeyCache = { password, key }

    return {
      key,
      meta: {
        cacheHit: false,
        ms: Math.round(end - start),
        iterations: PBKDF2_ITERATIONS,
        native: false,
      },
    }
  }

  async fernetDecrypt(
    encryptedData: Uint8Array,
    key: Buffer,
  ): Promise<FernetDecryptResult> {
    const start = nowMs()
    const plaintext = fernetDecryptJs(encryptedData, key)
    const end = nowMs()

    return {
      plaintext,
      meta: {
        ms: Math.round(end - start),
        native: false,
      },
    }
  }

  async zlibDecompress(data: Uint8Array): Promise<Uint8Array> {
    return pako.inflate(data)
  }
}

export const backupCrypto = new BackupCryptoService()
