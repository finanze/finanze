import { CryptoWalletConnection } from "@/domain"

export interface CryptoWalletConnectionPort {
  getByEntityId(entityId: string): Promise<CryptoWalletConnection[]>
  getByEntityAndAddress(
    entityId: string,
    address: string,
  ): Promise<CryptoWalletConnection | null>
  getConnectedEntities(): Promise<string>
  insert(connection: CryptoWalletConnection): Promise<void>
  rename(walletConnectionId: string, name: string): Promise<void>
  delete(walletConnectionId: string): Promise<void>
}
