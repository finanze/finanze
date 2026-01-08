import { Buffer } from "buffer"
import * as aesjs from "aes-js"
import { hmac as hmacSha256 } from "@noble/hashes/hmac.js"
import { pbkdf2 } from "@noble/hashes/pbkdf2.js"
import { sha256 } from "@noble/hashes/sha2.js"

import { BACKUP_SALT, KEY_LENGTH, PBKDF2_ITERATIONS } from "./constants"

function timingSafeEqual(a: Uint8Array, b: Uint8Array): boolean {
  if (a.length !== b.length) return false

  let diff = 0
  for (let i = 0; i < a.length; i++) {
    diff |= a[i] ^ b[i]
  }
  return diff === 0
}

export function deriveKeyJs(password: string): Buffer {
  const passwordBuffer = Buffer.from(password, "utf-8")
  const saltBuffer = Buffer.from(BACKUP_SALT, "utf-8")

  const keyBytes = pbkdf2(sha256, passwordBuffer, saltBuffer, {
    c: PBKDF2_ITERATIONS,
    dkLen: KEY_LENGTH,
  })

  return Buffer.from(keyBytes)
}

export function fernetDecryptJs(
  encryptedData: Uint8Array,
  key: Buffer,
): Buffer {
  const tokenBytes = Buffer.from(encryptedData)

  if (tokenBytes.length < 57) {
    throw new Error("Invalid Fernet token: too short")
  }

  const iv = tokenBytes.subarray(9, 25)
  const ciphertext = tokenBytes.subarray(25, tokenBytes.length - 32)
  const hmacBytes = tokenBytes.subarray(tokenBytes.length - 32)

  const signingKey = key.subarray(0, 16)
  const signedData = tokenBytes.subarray(0, tokenBytes.length - 32)
  const expectedHmac = Buffer.from(hmacSha256(sha256, signingKey, signedData))
  const actualHmac = Buffer.from(hmacBytes)

  if (expectedHmac.length !== actualHmac.length) {
    throw new Error("Invalid backup password")
  }

  if (!timingSafeEqual(expectedHmac, actualHmac)) {
    throw new Error("Invalid backup password")
  }

  const encryptionKey = key.subarray(16, 32)

  const aesCbc = new aesjs.ModeOfOperation.cbc(encryptionKey, iv)
  const plaintext = Buffer.from(aesCbc.decrypt(ciphertext))

  if (plaintext.length === 0) {
    throw new Error("Decryption resulted in empty data")
  }

  const padLength = plaintext[plaintext.length - 1]

  if (padLength > 16 || padLength === 0) {
    throw new Error("Invalid backup password (padding check failed)")
  }

  for (let i = 1; i <= padLength; i++) {
    if (plaintext[plaintext.length - i] !== padLength) {
      throw new Error("Invalid backup password (padding check failed)")
    }
  }

  return plaintext.subarray(0, plaintext.length - padLength)
}
