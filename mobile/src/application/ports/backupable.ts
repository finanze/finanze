export interface Backupable {
  getLastUpdated(): Promise<Date | null>
  importData(data: Uint8Array): Promise<void>
}
