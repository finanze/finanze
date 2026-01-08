export interface DeleteCryptoWalletConnection {
  execute(walletId: string): Promise<void>
}
