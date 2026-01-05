import { ConfigStoragePort } from "../ports"
import type { GetDefaultCurrency } from "@/domain/usecases"

export class GetDefaultCurrencyImpl implements GetDefaultCurrency {
  constructor(private readonly configStorage: ConfigStoragePort) {}

  async execute(): Promise<string> {
    const currency = await this.configStorage.getDefaultCurrency()
    return currency?.trim() ? currency : "EUR"
  }
}
