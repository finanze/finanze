import { UpdateCryptoWalletConnection as UpdateCryptoWalletConnectionRequest } from "@/domain"

export interface UpdateCryptoWalletConnection {
  execute(data: UpdateCryptoWalletConnectionRequest): Promise<void>
}
