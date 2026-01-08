export interface DeleteManualTransaction {
  execute(txId: string): Promise<void>
}
