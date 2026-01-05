import crypto from "react-native-quick-crypto"
import pako from "pako"
import { Buffer } from "buffer"
import "fast-text-encoding"
import { BackupProcessRequest, BackupProcessResult } from "@/domain"
import { BackupProcessor } from "../../application/ports"

const BACKUP_SALT = "finanze-backup-salt"
const BACKUP_SALT_BUFFER = Buffer.from(BACKUP_SALT, "utf-8")
const PBKDF2_ITERATIONS = 100000
const KEY_LENGTH = 32 // 256 bits

/**
 * Derive encryption key from password using PBKDF2 (Sync)
 */
function deriveKey(hashedPassword: string): Buffer {
  const passwordBuffer = Buffer.from(hashedPassword, "utf-8")

  return crypto.pbkdf2Sync(
    passwordBuffer,
    BACKUP_SALT_BUFFER,
    PBKDF2_ITERATIONS,
    KEY_LENGTH,
    "sha256" as any,
  ) as unknown as Buffer
}

/**
 * Base64 URL-safe decode (Fernet uses URL-safe base64)
 */
function base64UrlDecode(input: string): Buffer {
  let base64 = input.replace(/-/g, "+").replace(/_/g, "/")

  while (base64.length % 4 !== 0) {
    base64 += "="
  }

  return Buffer.from(base64, "base64")
}

/**
 * Base64 URL-safe encode
 */
function base64UrlEncode(data: Uint8Array): string {
  const buf = Buffer.from(data)
  return buf
    .toString("base64")
    .replace(/\+/g, "-")
    .replace(/\//g, "_")
    .replace(/=/g, "")
}

/**
 * Decrypt Fernet-encrypted data manually to avoid lib padding errors
 */
function fernetDecrypt(encryptedData: Uint8Array, key: Buffer): Buffer {
  const tokenBytes = Buffer.from(encryptedData)

  if (tokenBytes.length < 57) {
    throw new Error("Invalid Fernet token: too short")
  }

  const version = tokenBytes[0]
  if (version !== 0x80) {
    // Best-effort: continue.
  }

  // Extract components
  const iv = tokenBytes.subarray(9, 25)
  const ciphertext = tokenBytes.subarray(25, tokenBytes.length - 32)
  const hmac = tokenBytes.subarray(tokenBytes.length - 32)

  // Split key: First 16 bytes = Signing, Last 16 bytes = Encryption
  // (Fernet spec: Key is 32 URL-safe base64 bytes, decoded to 32 bytes)
  // Python: key = base64.urlsafe_b64encode(kdf_output)
  // Fernet(key) -> converts base64 back to 32 bytes
  // So we use the RAW KDF output (32 bytes).

  const signingKey = key.subarray(0, 16)
  const signedData = tokenBytes.subarray(0, tokenBytes.length - 32)
  const expectedHmac = Buffer.from(
    crypto.createHmac("sha256", signingKey).update(signedData).digest(),
  )
  const actualHmac = Buffer.from(hmac)

  if (expectedHmac.length !== actualHmac.length) {
    throw new Error("Invalid backup password")
  }

  if (!crypto.timingSafeEqual(expectedHmac, actualHmac)) {
    throw new Error("Invalid backup password")
  }

  const encryptionKey = key.subarray(16, 32)

  // Decrypt using AES-128-CBC
  const decipher = crypto.createDecipheriv("aes-128-cbc", encryptionKey, iv)

  // CRITICAL: Disable auto padding to prevent crashes on 'final'
  // We will remove PKCS7 padding manually
  decipher.setAutoPadding(false)

  let decrypted = decipher.update(ciphertext)
  const final = decipher.final()

  const plaintext = Buffer.concat([decrypted, final])

  // Manual PKCS7 unpadding
  if (plaintext.length === 0) {
    throw new Error("Decryption resulted in empty data")
  }

  const padLength = plaintext[plaintext.length - 1]

  // Validate padding
  if (padLength > 16 || padLength === 0) {
    // This is the surest sign of a wrong key (bad decryption)
    throw new Error("Invalid backup password (padding check failed)")
  }

  // Verify all padding bytes
  for (let i = 1; i <= padLength; i++) {
    if (plaintext[plaintext.length - i] !== padLength) {
      throw new Error("Invalid backup password (padding check failed)")
    }
  }

  // Return unpadded data
  return plaintext.subarray(0, plaintext.length - padLength)
}

/**
 * Decompress zlib-compressed data
 */
function zlibDecompress(data: Uint8Array): Uint8Array {
  return pako.inflate(data)
}

/**
 * Process (decrypt and decompress) a backup piece
 */
async function decompileBackup(
  payload: Uint8Array,
  password: string,
  protocol: number = 1,
): Promise<BackupProcessResult> {
  if (protocol !== 1) {
    throw new Error(`Unsupported backup protocol: ${protocol}`)
  }

  try {
    // Step 1: Derive key from password
    const key = deriveKey(password)

    // Step 2: Decrypt with Fernet (Manual)
    const decryptedBuffer = fernetDecrypt(payload, key)

    // Step 3: Decompress with zlib
    const decompressed = zlibDecompress(decryptedBuffer)

    return { payload: decompressed }
  } catch (error: any) {
    if (
      error.message?.includes("password") ||
      error.message?.includes("padding") ||
      error.message?.includes("decrypt") ||
      error.message?.includes("incorrect header") // pako error
    ) {
      throw new Error("Invalid backup password")
    }
    throw error
  }
}

export class BackupProcessorService implements BackupProcessor {
  async decompile(request: BackupProcessRequest): Promise<BackupProcessResult> {
    return decompileBackup(request.payload, request.password, request.protocol)
  }

  async compile(): Promise<BackupProcessResult> {
    throw new Error("Not implemented")
  }
}

export const backupProcessor = new BackupProcessorService()

export default { BackupProcessorService, backupProcessor }
