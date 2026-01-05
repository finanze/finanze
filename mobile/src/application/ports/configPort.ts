export interface ConfigStoragePort {
  saveConfig(data: Uint8Array, lastUpdated?: Date): Promise<void>
  getConfig(): Promise<Uint8Array | null>
  getLastUpdated(): Promise<Date>
  getDefaultCurrency(): Promise<string | null>
  clearConfig(): Promise<void>
}
