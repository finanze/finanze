import { TransactionQueryRequest, TransactionsResult } from "@/domain"
import { TransactionPort, EntityPort } from "../ports"
import { GetTransactions } from "@/domain/usecases"

export class GetTransactionsImpl implements GetTransactions {
  constructor(
    private transactionPort: TransactionPort,
    private entityPort: EntityPort,
  ) {}

  async execute(query: TransactionQueryRequest): Promise<TransactionsResult> {
    const disabledEntities = await this.entityPort.getDisabledEntities()
    const excludedEntities = disabledEntities
      .map(e => e.id)
      .filter((id): id is string => Boolean(id))

    const fullQuery: TransactionQueryRequest = {
      ...query,
      excludedEntities,
    }

    const transactions = await this.transactionPort.getByFilters(fullQuery)

    return { transactions }
  }
}
