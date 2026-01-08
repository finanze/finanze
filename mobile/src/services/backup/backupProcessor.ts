import { Buffer } from "buffer"
import "fast-text-encoding"
import { BackupProcessRequest, BackupProcessResult } from "@/domain"
import { BackupProcessor } from "../../application/ports"
import { backupCrypto } from "./crypto"

/**
 * Process (decrypt and decompress) a backup piece
 */
async function decompileBackup(
  payload: Uint8Array,
  key: Buffer,
  protocol: number = 1,
): Promise<BackupProcessResult> {
  if (protocol !== 1) {
    throw new Error(`Unsupported backup protocol: ${protocol}`)
  }

  try {
    // Step 2: Decrypt with Fernet (Manual)
    const decryptResult = await backupCrypto.fernetDecrypt(payload, key)

    // Step 3: Decompress with zlib
    const decompressed = await backupCrypto.zlibDecompress(
      decryptResult.plaintext,
    )

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
    const deriveResult = await backupCrypto.deriveKey(request.password)

    return decompileBackup(request.payload, deriveResult.key, request.protocol)
  }

  async compile(): Promise<BackupProcessResult> {
    throw new Error("Not implemented")
  }
}

export const backupProcessor = new BackupProcessorService()

export default { BackupProcessorService, backupProcessor }
