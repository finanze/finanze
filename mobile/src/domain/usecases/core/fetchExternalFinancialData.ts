import { ExternalFetchRequest, FetchResult } from "@/domain"

export interface FetchExternalFinancialData {
  execute(fetchRequest: ExternalFetchRequest): Promise<FetchResult>
}
