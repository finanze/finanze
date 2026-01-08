import {
  ConnectCryptoWallet as ConnectCryptoWalletRequest,
  CryptoWalletConnectionResult,
} from "@/domain"

export interface ConnectCryptoWallet {
  execute(
    data: ConnectCryptoWalletRequest,
  ): Promise<CryptoWalletConnectionResult>
}
