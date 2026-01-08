import { CloudAuthData } from "./cloudAuth"

export enum BackupFileType {
  DATA = "DATA",
  CONFIG = "CONFIG",
}

export enum BackupMode {
  OFF = "OFF",
  MANUAL = "MANUAL",
  AUTO = "AUTO",
}

export interface BackupInfo {
  id: string
  protocol: number
  date: string
  type: BackupFileType
  size: number
}

export interface BackupsInfo {
  pieces: Partial<Record<BackupFileType, BackupInfo>>
}

export interface BackupsInfoRequest {
  onlyLocal?: boolean
}

export enum SyncStatus {
  SYNC = "SYNC",
  PENDING = "PENDING",
  OUTDATED = "OUTDATED",
  MISSING = "MISSING",
  CONFLICT = "CONFLICT",
}

export interface FullBackupInfo {
  local: BackupInfo | null
  remote: BackupInfo | null
  lastUpdate: string
  hasLocalChanges: boolean
  status: SyncStatus | null
}

export interface FullBackupsInfo {
  pieces: Partial<Record<BackupFileType, FullBackupInfo>>
}

export interface BackupProcessRequest {
  protocol: number
  password: string
  payload: Uint8Array
}

export interface BackupProcessResult {
  payload: Uint8Array
}

export interface BackupTransferPiece {
  id: string
  protocol: number
  date: string
  type: BackupFileType
  payload: Uint8Array
}

export interface BackupPieces {
  pieces: BackupTransferPiece[]
}

export interface BackupUploadParams {
  pieces: BackupPieces
  auth: CloudAuthData
}

export interface BackupDownloadParams {
  types: BackupFileType[]
  auth: CloudAuthData
}

export interface BackupInfoParams {
  auth: CloudAuthData
}

export interface UploadBackupRequest {
  types: BackupFileType[]
  force?: boolean
}

export interface ImportBackupRequest {
  types: BackupFileType[]
  password: string | null
  force?: boolean
}

export interface BackupSyncResult {
  pieces: Partial<Record<BackupFileType, FullBackupInfo>>
}

export interface BackupSettings {
  mode: BackupMode
}
