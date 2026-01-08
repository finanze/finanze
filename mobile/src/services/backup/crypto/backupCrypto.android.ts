import pako from "pako"
import { Buffer } from "buffer"
import { NativeModules, Platform } from "react-native"

import { BACKUP_SALT, KEY_LENGTH, PBKDF2_ITERATIONS } from "./constants"
import type { DeriveKeyResult, FernetDecryptResult } from "./types"
import { deriveKeyJs, fernetDecryptJs } from "./jsImpl"

type DerivedKeyCache = { password: string; key: Buffer } | null

type FinanzeCryptoNativeModule = {
  pbkdf2Sha256: (
    password: string,
    salt: string,
    iterations: number,
    keyLen: number,
  ) => Promise<string>
  fernetDecrypt?: (tokenB64: string, keyB64: string) => Promise<string>
}

const FinanzeCrypto = (NativeModules as any)?.FinanzeCrypto as
  | FinanzeCryptoNativeModule
  | undefined

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
          native: true,
        },
      }
    }

    const start = nowMs()

    let key: Buffer
    let native = false

    if (
      Platform.OS === "android" &&
      FinanzeCrypto &&
      typeof FinanzeCrypto.pbkdf2Sha256 === "function"
    ) {
      try {
        const b64 = await FinanzeCrypto.pbkdf2Sha256(
          password,
          BACKUP_SALT,
          PBKDF2_ITERATIONS,
          KEY_LENGTH,
        )
        key = Buffer.from(b64, "base64")
        native = true
      } catch {
        key = deriveKeyJs(password)
      }
    } else {
      key = deriveKeyJs(password)
    }

    const end = nowMs()

    this.derivedKeyCache = { password, key }

    return {
      key,
      meta: {
        cacheHit: false,
        ms: Math.round(end - start),
        iterations: PBKDF2_ITERATIONS,
        native,
      },
    }
  }

  async fernetDecrypt(
    encryptedData: Uint8Array,
    key: Buffer,
  ): Promise<FernetDecryptResult> {
    const start = nowMs()

    let plaintext: Buffer
    let native = false

    if (
      Platform.OS === "android" &&
      FinanzeCrypto &&
      typeof FinanzeCrypto.fernetDecrypt === "function"
    ) {
      try {
        const tokenB64 = Buffer.from(encryptedData).toString("base64")
        const keyB64 = Buffer.from(key).toString("base64")
        const plainB64 = await FinanzeCrypto.fernetDecrypt(tokenB64, keyB64)
        plaintext = Buffer.from(plainB64, "base64")
        native = true
      } catch {
        plaintext = fernetDecryptJs(encryptedData, key)
      }
    } else {
      plaintext = fernetDecryptJs(encryptedData, key)
    }

    const end = nowMs()

    return {
      plaintext,
      meta: {
        ms: Math.round(end - start),
        native,
      },
    }
  }

  async zlibDecompress(data: Uint8Array): Promise<Uint8Array> {
    return pako.inflate(data)
  }
}

export const backupCrypto = new BackupCryptoService()
