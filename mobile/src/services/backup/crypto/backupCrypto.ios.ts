import pako from "pako"
import { Buffer } from "buffer"
import crypto from "react-native-quick-crypto"

import { BACKUP_SALT, KEY_LENGTH, PBKDF2_ITERATIONS } from "./constants"
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
          native: true,
        },
      }
    }

    const start = nowMs()

    let key: Buffer
    let native = true

    try {
      const out = crypto.pbkdf2Sync(
        Buffer.from(password, "utf-8"),
        Buffer.from(BACKUP_SALT, "utf-8"),
        PBKDF2_ITERATIONS,
        KEY_LENGTH,
        "SHA-256",
      )
      key = Buffer.from(out)
    } catch {
      // If quick-crypto isn't available in a given build, fall back.
      key = deriveKeyJs(password)
      native = false
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
    let native = true

    try {
      const tokenBytes = Buffer.from(encryptedData)

      if (tokenBytes.length < 57) {
        throw new Error("Invalid Fernet token: too short")
      }

      const iv = tokenBytes.subarray(9, 25)
      const ciphertext = tokenBytes.subarray(25, tokenBytes.length - 32)
      const hmacBytes = tokenBytes.subarray(tokenBytes.length - 32)

      const signingKey = key.subarray(0, 16)
      const signedData = tokenBytes.subarray(0, tokenBytes.length - 32)
      const expectedHmac = crypto
        .createHmac("sha256", signingKey)
        .update(signedData)
        .digest()
      const actualHmac = Buffer.from(hmacBytes)

      if (expectedHmac.length !== actualHmac.length) {
        throw new Error("Invalid backup password")
      }

      if (!crypto.timingSafeEqual(expectedHmac, actualHmac)) {
        throw new Error("Invalid backup password")
      }

      const encryptionKey = key.subarray(16, 32)

      const decipher = crypto.createDecipheriv("aes-128-cbc", encryptionKey, iv)

      plaintext = Buffer.concat([
        Buffer.from(decipher.update(ciphertext)),
        Buffer.from(decipher.final()),
      ])
    } catch (error: any) {
      // Fall back to JS implementation on missing native crypto.
      try {
        plaintext = fernetDecryptJs(encryptedData, key)
        native = false
      } catch {
        throw error
      }
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
