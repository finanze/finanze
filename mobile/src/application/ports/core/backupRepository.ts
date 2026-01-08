import {
  BackupDownloadParams,
  BackupInfoParams,
  BackupPieces,
  BackupUploadParams,
  BackupsInfo,
} from "@/domain"

export interface BackupRepository {
  upload(request: BackupUploadParams): Promise<BackupPieces>
  download(request: BackupDownloadParams): Promise<BackupPieces>
  getInfo(request: BackupInfoParams): Promise<BackupsInfo>
}
