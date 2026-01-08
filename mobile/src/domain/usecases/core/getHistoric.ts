import { Historic, HistoricQueryRequest } from "@/domain"

export interface GetHistoric {
  execute(query: HistoricQueryRequest): Promise<Historic>
}
