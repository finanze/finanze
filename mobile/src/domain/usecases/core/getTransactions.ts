import { TransactionQueryRequest, TransactionsResult } from "@/domain"

export interface GetTransactions {
  execute(query: TransactionQueryRequest): Promise<TransactionsResult>
}
