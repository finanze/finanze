import { FetchRequest, FetchResult } from "@/domain"

export interface FetchCryptoData {
  execute(fetchRequest: FetchRequest): Promise<FetchResult>
}
