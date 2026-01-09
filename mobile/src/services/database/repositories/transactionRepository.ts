import { DataManager } from "../dataManager"
import {
  BaseTx,
  AccountTx,
  StockTx,
  CryptoCurrencyTx,
  FundTx,
  FundPortfolioTx,
  BaseInvestmentTx,
  TxType,
  DataSource,
  ProductType,
  EquityType,
  FundType,
  Entity,
  TransactionQueryRequest,
  Transactions,
} from "@/domain"
import { parseDezimalValue } from "@/domain"
import { TransactionPort } from "@/application/ports"
import { TransactionQueries } from "./queries"

export class TransactionRepository implements TransactionPort {
  constructor(private client: DataManager) {}

  async save(data: Transactions): Promise<void> {
    const now = new Date().toISOString()
    await this.client.transaction(async () => {
      for (const tx of data.investment ?? []) {
        if (!tx.entity?.id || !tx.id) continue
        await this.client.execute(TransactionQueries.INSERT_INVESTMENT, {
          id: tx.id,
          ref: tx.ref,
          name: tx.name,
          amount: String(tx.amount),
          currency: tx.currency,
          type: tx.type,
          date: tx.date,
          entity_id: tx.entity.id,
          is_real: tx.source === DataSource.REAL ? 1 : 0,
          source: tx.source,
          product_type: tx.productType,
          created_at: now,
          isin: (tx as any).isin ?? null,
          ticker: (tx as any).ticker ?? (tx as any).symbol ?? null,
          asset_contract_address: (tx as any).contractAddress ?? null,
          market: (tx as any).market ?? null,
          shares: String((tx as any).shares ?? (tx as any).currencyAmount ?? 0),
          price: String((tx as any).price ?? 0),
          net_amount:
            (tx as any).netAmount != null
              ? String((tx as any).netAmount)
              : null,
          fees: String((tx as any).fees ?? 0),
          retentions:
            (tx as any).retentions != null
              ? String((tx as any).retentions)
              : null,
          order_date: (tx as any).orderDate ?? null,
          linked_tx: (tx as any).linkedTx ?? null,
          interests: (tx as any).interests ?? null,
          iban: (tx as any).iban ?? null,
          portfolio_name: (tx as any).portfolioName ?? null,
          product_subtype:
            (tx as any).equityType ?? (tx as any).fundType ?? null,
        } as any)
      }

      for (const tx of data.account ?? []) {
        if (!tx.entity?.id || !tx.id) continue
        await this.client.execute(TransactionQueries.INSERT_ACCOUNT, [
          tx.id,
          tx.ref,
          tx.name,
          String(tx.amount),
          tx.currency,
          tx.type,
          tx.date,
          tx.entity.id,
          tx.source === DataSource.REAL ? 1 : 0,
          tx.source,
          now,
          String(tx.fees ?? 0),
          String(tx.retentions ?? 0),
          tx.interestRate != null ? String(tx.interestRate) : null,
          tx.avgBalance != null ? String(tx.avgBalance) : null,
          tx.netAmount != null ? String(tx.netAmount) : null,
        ])
      }
    })
  }

  async getAll(
    real?: boolean | null,
    excludedEntities?: string[] | null,
  ): Promise<Transactions> {
    const investmentConditions: string[] = []
    const accountConditions: string[] = []
    const paramsInvestment: any[] = []
    const paramsAccount: any[] = []

    if (real != null) {
      investmentConditions.push("it.is_real = ?")
      accountConditions.push("at.is_real = ?")
      paramsInvestment.push(real ? 1 : 0)
      paramsAccount.push(real ? 1 : 0)
    }

    if (excludedEntities && excludedEntities.length > 0) {
      const placeholders = excludedEntities.map(() => "?").join(",")
      investmentConditions.push(`it.entity_id NOT IN (${placeholders})`)
      accountConditions.push(`at.entity_id NOT IN (${placeholders})`)
      paramsInvestment.push(...excludedEntities)
      paramsAccount.push(...excludedEntities)
    }

    const investmentSql =
      TransactionQueries.INVESTMENT_SELECT_BASE +
      (investmentConditions.length > 0
        ? ` WHERE ${investmentConditions.join(" AND ")}`
        : "")
    const accountSql =
      TransactionQueries.ACCOUNT_SELECT_BASE +
      (accountConditions.length > 0
        ? ` WHERE ${accountConditions.join(" AND ")}`
        : "")

    const [investment, account] = await Promise.all([
      this.client.query<any>(investmentSql, paramsInvestment),
      this.client.query<any>(accountSql, paramsAccount),
    ])

    return {
      investment: investment.rows.map(r => this.mapRowToTransaction({ ...r })),
      account: account.rows.map(r =>
        this.mapRowToTransaction({ ...r, product_type: "ACCOUNT" }),
      ) as any,
    }
  }

  async getRefsByEntity(entityId: string): Promise<any> {
    const res = await this.client.query<any>(
      TransactionQueries.GET_REFS_BY_ENTITY,
      [entityId, entityId],
    )
    return res.rows.map((r: any) => r.ref)
  }

  async getByEntity(entityId: string): Promise<Transactions> {
    const [investment, account] = await Promise.all([
      this.client.query<any>(TransactionQueries.INVESTMENT_SELECT_BY_ENTITY, [
        entityId,
      ]),
      this.client.query<any>(TransactionQueries.ACCOUNT_SELECT_BY_ENTITY, [
        entityId,
      ]),
    ])

    return {
      investment: investment.rows.map(r => this.mapRowToTransaction({ ...r })),
      account: account.rows.map(r =>
        this.mapRowToTransaction({ ...r, product_type: "ACCOUNT" }),
      ) as any,
    }
  }

  async getByEntityAndSource(
    entityId: string,
    source: DataSource,
  ): Promise<Transactions> {
    const [investment, account] = await Promise.all([
      this.client.query<any>(
        TransactionQueries.INVESTMENT_AND_ACCOUNT_BY_ENTITY_AND_SOURCE,
        [entityId, source],
      ),
      this.client.query<any>(TransactionQueries.ACCOUNT_BY_ENTITY_AND_SOURCE, [
        entityId,
        source,
      ]),
    ])

    return {
      investment: investment.rows.map(r => this.mapRowToTransaction({ ...r })),
      account: account.rows.map(r =>
        this.mapRowToTransaction({ ...r, product_type: "ACCOUNT" }),
      ) as any,
    }
  }

  async getRefsBySourceType(real: boolean): Promise<any> {
    const res = await this.client.query<any>(
      TransactionQueries.GET_REFS_BY_SOURCE_TYPE,
      [real ? 1 : 0, real ? 1 : 0],
    )
    return res.rows.map((r: any) => r.ref)
  }

  async deleteBySource(source: DataSource): Promise<void> {
    await this.client.transaction(async () => {
      await this.client.execute(
        TransactionQueries.DELETE_INVESTMENT_BY_SOURCE,
        [source],
      )
      await this.client.execute(TransactionQueries.DELETE_ACCOUNT_BY_SOURCE, [
        source,
      ])
    })
  }

  async deleteByEntitySource(
    entityId: string,
    source: DataSource,
  ): Promise<void> {
    await this.client.transaction(async () => {
      await this.client.execute(
        TransactionQueries.DELETE_INVESTMENT_BY_ENTITY_SOURCE,
        [entityId, source],
      )
      await this.client.execute(
        TransactionQueries.DELETE_ACCOUNT_BY_ENTITY_SOURCE,
        [entityId, source],
      )
    })
  }

  async getById(txId: string): Promise<BaseTx | null> {
    const [inv, acc] = await Promise.all([
      this.client.query<any>(TransactionQueries.GET_INVESTMENT_BY_ID, [txId]),
      this.client.query<any>(TransactionQueries.GET_ACCOUNT_BY_ID, [txId]),
    ])
    if (inv.rows.length > 0) return this.mapRowToTransaction(inv.rows[0])
    if (acc.rows.length > 0)
      return this.mapRowToTransaction({
        ...acc.rows[0],
        product_type: "ACCOUNT",
      })
    return null
  }

  async deleteById(txId: string): Promise<void> {
    await this.client.transaction(async () => {
      await this.client.execute(TransactionQueries.DELETE_BY_ID_INVESTMENT, [
        txId,
      ])
      await this.client.execute(TransactionQueries.DELETE_BY_ID_ACCOUNT, [txId])
    })
  }

  async getByFilters(query: TransactionQueryRequest): Promise<BaseTx[]> {
    const params: any[] = []
    let whereConditions: string[] = []

    if (query.excludedEntities && query.excludedEntities.length > 0) {
      const placeholders = query.excludedEntities.map(() => "?").join(", ")
      whereConditions.push(`tx.entity_id NOT IN (${placeholders})`)
      params.push(...query.excludedEntities)
    }

    if (query.entities && query.entities.length > 0) {
      const placeholders = query.entities.map(() => "?").join(", ")
      whereConditions.push(`tx.entity_id IN (${placeholders})`)
      params.push(...query.entities)
    }

    if (query.fromDate) {
      whereConditions.push(`tx.date >= ?`)
      params.push(query.fromDate)
    }

    if (query.toDate) {
      whereConditions.push(`tx.date <= ?`)
      params.push(query.toDate)
    }

    if (query.productTypes && query.productTypes.length > 0) {
      const placeholders = query.productTypes.map(() => "?").join(", ")
      whereConditions.push(`tx.product_type IN (${placeholders})`)
      params.push(...query.productTypes)
    }

    if (query.types && query.types.length > 0) {
      const placeholders = query.types.map(() => "?").join(", ")
      whereConditions.push(`tx.type IN (${placeholders})`)
      params.push(...query.types)
    }

    const whereClause =
      whereConditions.length > 0 ? `WHERE ${whereConditions.join(" AND ")}` : ""

    const limit = query.limit || 100
    const page = query.page || 1
    const offset = (page - 1) * limit
    params.push(limit, offset)

    const sql = `
      ${TransactionQueries.GET_BY_FILTERS_BASE}
      ${whereClause}
      ORDER BY tx.date DESC
      LIMIT ? OFFSET ?
    `

    const result = await this.client.query<any>(sql, params)
    return result.rows.map(this.mapRowToTransaction)
  }

  async getRecentTransactions(limit: number = 10): Promise<BaseTx[]> {
    const sql = `
      ${TransactionQueries.GET_BY_FILTERS_BASE}
      ORDER BY tx.date DESC
      LIMIT ?
    `

    const result = await this.client.query<any>(sql, [limit])
    return result.rows.map(this.mapRowToTransaction)
  }

  async getTransactionsByEntity(
    entityId: string,
    limit: number = 50,
  ): Promise<BaseTx[]> {
    const sql = `
      ${TransactionQueries.GET_BY_FILTERS_BASE}
      WHERE tx.entity_id = ?
      ORDER BY tx.date DESC
      LIMIT ?
    `
    const result = await this.client.query<any>(sql, [entityId, limit])
    return result.rows.map(this.mapRowToTransaction)
  }

  async getTransactionsByDateRange(
    startDate: Date,
    endDate: Date,
    limit: number = 100,
  ): Promise<BaseTx[]> {
    const s = startDate.toISOString()
    const e = endDate.toISOString()
    const sql = `
      ${TransactionQueries.GET_BY_FILTERS_BASE}
      WHERE tx.date >= ? AND tx.date <= ?
      ORDER BY tx.date DESC
      LIMIT ?
    `
    const result = await this.client.query<any>(sql, [s, e, limit])
    return result.rows.map(this.mapRowToTransaction)
  }

  private mapRowToTransaction(row: any): BaseTx {
    const entity: Entity = {
      id: row.entity_id,
      name: row.entity_name,
      naturalId: row.entity_natural_id ?? null,
      type: row.entity_type,
      origin: row.entity_origin,
      iconUrl: row.icon_url,
    }

    const base: BaseTx = {
      id: row.id,
      ref: row.ref,
      name: row.name,
      amount: parseDezimalValue(row.amount),
      currency: row.currency,
      type: row.type as TxType,
      date: row.date,
      entity: entity,
      source: row.source as DataSource,
      productType: row.product_type as ProductType,
    }

    if (row.product_type === "ACCOUNT") {
      return {
        ...base,
        fees: parseDezimalValue(row.fees),
        retentions: parseDezimalValue(row.retentions),
        interestRate:
          row.interest_rate != null
            ? parseDezimalValue(row.interest_rate)
            : null,
        avgBalance:
          row.avg_balance != null ? parseDezimalValue(row.avg_balance) : null,
        netAmount:
          row.net_amount != null ? parseDezimalValue(row.net_amount) : null,
      } as AccountTx
    }

    // Investment Transactions
    const investmentBase: BaseInvestmentTx = { ...base }

    if (row.product_type === ProductType.STOCK_ETF) {
      return {
        ...investmentBase,
        shares: parseDezimalValue(row.shares),
        price: parseDezimalValue(row.price),
        fees: parseDezimalValue(row.fees),
        netAmount:
          row.net_amount != null ? parseDezimalValue(row.net_amount) : null,
        isin: row.isin,
        ticker: row.ticker,
        market: row.market,
        retentions:
          row.retentions != null ? parseDezimalValue(row.retentions) : null,
        orderDate: row.order_date,
        linkedTx: row.linked_tx,
        equityType: row.product_subtype as EquityType,
      } as StockTx
    } else if (row.product_type === ProductType.CRYPTO) {
      return {
        ...investmentBase,
        currencyAmount: parseDezimalValue(row.shares), // mapped from shares
        symbol: row.ticker, // mapped from ticker
        price: parseDezimalValue(row.price),
        fees: parseDezimalValue(row.fees),
        contractAddress: row.asset_contract_address,
        netAmount:
          row.net_amount != null ? parseDezimalValue(row.net_amount) : null,
        retentions:
          row.retentions != null ? parseDezimalValue(row.retentions) : null,
        orderDate: row.order_date,
      } as CryptoCurrencyTx
    } else if (row.product_type === ProductType.FUND) {
      return {
        ...investmentBase,
        shares: parseDezimalValue(row.shares),
        price: parseDezimalValue(row.price),
        fees: parseDezimalValue(row.fees),
        netAmount:
          row.net_amount != null ? parseDezimalValue(row.net_amount) : null,
        isin: row.isin,
        market: row.market,
        retentions:
          row.retentions != null ? parseDezimalValue(row.retentions) : null,
        orderDate: row.order_date,
        fundType: row.product_subtype as FundType,
      } as FundTx
    } else if (row.product_type === ProductType.FUND_PORTFOLIO) {
      return {
        ...investmentBase,
        portfolioName: row.portfolio_name,
        iban: row.iban,
        fees: row.fees != null ? parseDezimalValue(row.fees) : undefined,
      } as FundPortfolioTx
    }

    // Default fallback for other investment types
    return investmentBase
  }
}
