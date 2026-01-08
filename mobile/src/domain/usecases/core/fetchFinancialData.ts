import { FetchRequest, FetchResult } from "@/domain"

export interface FetchFinancialData {
  execute(fetchRequest: FetchRequest): Promise<FetchResult>
}
