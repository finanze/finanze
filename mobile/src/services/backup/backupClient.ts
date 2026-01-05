import { Config } from "../../config"
import {
  BackupFileType,
  BackupsInfo,
  BackupInfo,
  BackupTransferPiece,
  BackupInfoParams,
  BackupDownloadParams,
  BackupUploadParams,
  BackupPieces,
} from "@/domain"
import { BackupRepository } from "@/application/ports"

export interface BackupDownloadPiece {
  id: string
  protocol: number
  date: string
  type: BackupFileType
  url: string
}

export interface BackupDownloadResponse {
  pieces: Record<string, BackupDownloadPiece>
}

export class BackupClient implements BackupRepository {
  private baseUrl: string

  constructor() {
    this.baseUrl = Config.CLOUD_API_URL!
  }

  private getAuthHeaders(accessToken: string): Record<string, string> {
    return {
      Authorization: `Bearer ${accessToken}`,
      "Content-Type": "application/json",
    }
  }

  /**
   * Get information about available backups in the cloud
   */
  async getInfo(params: BackupInfoParams): Promise<BackupsInfo> {
    const response = await fetch(`${this.baseUrl}/v1/backups`, {
      method: "GET",
      headers: this.getAuthHeaders(params.auth.token.accessToken),
    })

    if (response.status === 429) {
      throw new Error("Too many requests. Please try again later.")
    }

    if (!response.ok) {
      throw new Error(
        `Failed to get backup info: ${response.statusText} ${response.status}`,
      )
    }

    const data = await response.json()
    const pieces: Record<BackupFileType, BackupInfo> = {} as any

    for (const [type, info] of Object.entries(data.pieces || {})) {
      const pieceInfo = info as any
      pieces[type as BackupFileType] = {
        id: pieceInfo.id,
        protocol: pieceInfo.protocol,
        date: pieceInfo.date,
        type: type as BackupFileType,
        size: pieceInfo.size,
      }
    }

    return { pieces }
  }

  /**
   * Download backup pieces from the cloud storage
   */
  async download(
    params: BackupDownloadParams,
  ): Promise<{ pieces: BackupTransferPiece[] }> {
    if (params.types.length === 0) {
      return { pieces: [] }
    }

    // Request download URLs
    const urlParams = params.types.map(t => `type=${t}`).join("&")
    const response = await fetch(
      `${this.baseUrl}/v1/backups/download?${urlParams}`,
      {
        method: "GET",
        headers: this.getAuthHeaders(params.auth.token.accessToken),
      },
    )

    if (response.status === 429) {
      throw new Error("Too many requests. Please try again later.")
    }

    if (!response.ok) {
      throw new Error(`Failed to get download URLs: ${response.statusText}`)
    }

    const downloadResponse: BackupDownloadResponse = await response.json()
    const pieces: BackupTransferPiece[] = []

    // Download each piece from the presigned URL
    for (const [typeStr, pieceInfo] of Object.entries(
      downloadResponse.pieces || {},
    )) {
      if (!pieceInfo.url) {
        console.warn(`No URL found for backup type ${typeStr}`)
        continue
      }

      try {
        const payloadResponse = await fetch(pieceInfo.url)

        if (!payloadResponse.ok) {
          console.error(`Failed to download piece ${typeStr}`)
          continue
        }

        const arrayBuffer = await payloadResponse.arrayBuffer()
        const payload = new Uint8Array(arrayBuffer)

        pieces.push({
          id: pieceInfo.id,
          protocol: pieceInfo.protocol,
          date: pieceInfo.date,
          type: pieceInfo.type as BackupFileType,
          payload,
        })

        console.log(`Successfully downloaded backup piece: ${typeStr}`)
      } catch (error) {
        console.error(`Error downloading piece ${typeStr}:`, error)
        continue
      }
    }

    return { pieces }
  }

  async upload(request: BackupUploadParams): Promise<BackupPieces> {
    throw new Error("Not implemented")
  }
}

export const backupClient = new BackupClient()
