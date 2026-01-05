import { DataManager } from "../dataManager"
import {
  FundDetail,
  GlobalPosition,
  ProductType,
  Entity,
  PositionQueryRequest,
  DataSource,
  StockDetail,
} from "@/domain"
import { Dezimal } from "@/domain/dezimal"
import { PositionPort } from "@/application/ports"
import { PositionQueries } from "./queries"

export class PositionRepository implements PositionPort {
  constructor(private client: DataManager) {}

  async save(position: GlobalPosition): Promise<void> {
    await this.client.execute(PositionQueries.INSERT_GLOBAL_POSITION, [
      position.id,
      position.date,
      position.entity.id,
      position.source,
    ])
  }

  async deletePositionForDate(
    entityId: string,
    date: string,
    source: DataSource,
  ): Promise<void> {
    await this.client.execute(PositionQueries.DELETE_POSITION_FOR_DATE, [
      entityId,
      date,
      source,
    ])
  }

  async getById(positionId: string): Promise<GlobalPosition | null> {
    try {
      const res = await this.client.query<any>(
        PositionQueries.GET_GLOBAL_POSITION_BY_ID,
        [positionId],
      )
      if (res.rows.length === 0) return null

      const row = res.rows[0]
      const entity: Entity = {
        id: row.entity_id,
        name: row.entity_name,
        naturalId: row.entity_natural_id ?? null,
        type: row.entity_type,
        origin: row.entity_origin,
        iconUrl: row.icon_url ?? null,
      }

      const position: GlobalPosition = {
        id: row.id,
        entity,
        date: row.date,
        source: row.source,
        products: {},
      }

      position.products = await this._getProductPositions(position)
      return position
    } catch {
      return null
    }
  }

  async deleteById(positionId: string): Promise<void> {
    await this.client.execute(PositionQueries.DELETE_GLOBAL_POSITION_BY_ID, [
      positionId,
    ])
  }

  async getStockDetail(entryId: string): Promise<StockDetail | null> {
    try {
      const res = await this.client.query<any>(
        PositionQueries.GET_STOCK_DETAIL,
        [entryId],
      )
      if (res.rows.length === 0) return null
      const row = res.rows[0]
      return {
        ...(row as any),
        id: row.id,
        source: row.source,
      } as StockDetail
    } catch {
      return null
    }
  }

  async getFundDetail(entryId: string): Promise<FundDetail | null> {
    try {
      const res = await this.client.query<any>(
        PositionQueries.GET_FUND_DETAIL,
        [entryId],
      )
      if (res.rows.length === 0) return null
      const row = res.rows[0]
      return {
        ...(row as any),
        id: row.id,
        source: row.source,
      } as FundDetail
    } catch {
      return null
    }
  }

  async updateMarketValue(
    entryId: string,
    productType: ProductType,
    marketValue: Dezimal,
  ): Promise<void> {
    if (productType === ProductType.STOCK_ETF) {
      await this.client.execute(PositionQueries.UPDATE_STOCK_MARKET_VALUE, [
        String(marketValue),
        entryId,
      ])
      return
    }

    if (productType === ProductType.FUND) {
      await this.client.execute(PositionQueries.UPDATE_FUND_MARKET_VALUE, [
        String(marketValue),
        entryId,
      ])
    }
  }

  async getLastGroupedByEntity(
    query?: PositionQueryRequest | null,
  ): Promise<Map<Entity, GlobalPosition>> {
    const normalizedQuery = query ?? undefined
    const includeReal = !query || query.real == null || query.real
    const includeNonReal = !query || query.real == null || !query.real

    const realPositions = includeReal
      ? await this._getRealGroupedByEntity(normalizedQuery)
      : {}
    const nonRealPositions = includeNonReal
      ? await this._getNonRealGroupedByEntity(normalizedQuery)
      : {}

    const merged: Record<string, GlobalPosition> = {}

    for (const [entityId, position] of Object.entries(realPositions)) {
      const manualList = nonRealPositions[entityId]
      if (manualList && manualList.length > 0) {
        merged[entityId] = addGlobalPositions(
          position,
          aggregatePositions(manualList),
        )
        delete nonRealPositions[entityId]
      } else {
        merged[entityId] = position
      }
    }

    for (const [entityId, manualList] of Object.entries(nonRealPositions)) {
      merged[entityId] = aggregatePositions(manualList)
    }

    const out = new Map<Entity, GlobalPosition>()
    for (const position of Object.values(merged)) {
      out.set(position.entity, position)
    }
    return out
  }

  // Matching Python _get_real_grouped_by_entity
  private async _getRealGroupedByEntity(
    query?: PositionQueryRequest,
  ): Promise<Record<string, GlobalPosition>> {
    let sql: string = PositionQueries.REAL_GROUPED_BY_ENTITY_BASE

    const params: any[] = []
    const conditions: string[] = []

    if (query?.entities && query.entities.length > 0) {
      const placeholders = query.entities.map(() => "?").join(", ")
      conditions.push(`gp.entity_id IN (${placeholders})`)
      params.push(...query.entities)
    }

    if (query?.excludedEntities && query.excludedEntities.length > 0) {
      const placeholders = query.excludedEntities.map(() => "?").join(", ")
      conditions.push(`gp.entity_id NOT IN (${placeholders})`)
      params.push(...query.excludedEntities)
    }

    if (conditions.length > 0) {
      sql += " AND " + conditions.join(" AND ")
    }

    const result = await this.client.query<any>(sql, params)
    const map: Record<string, GlobalPosition> = {}

    for (const row of result.rows) {
      const entityId = row.entity_id as string
      const entity: Entity = {
        id: entityId,
        name: row.entity_name,
        naturalId: row.entity_natural_id ?? null,
        type: row.entity_type,
        origin: row.entity_origin,
        iconUrl: row.icon_url ?? null,
      }

      const position: GlobalPosition = {
        id: row.id,
        entity,
        date: row.date,
        source: row.source,
        products: {},
      }

      position.products = await this._getProductPositions(
        position,
        query?.products,
      )
      map[entityId] = position
    }

    return map
  }

  private async _getNonRealGroupedByEntity(
    query?: PositionQueryRequest,
  ): Promise<Record<string, GlobalPosition[]>> {
    const hasVirtualImports = await this.tableExists("virtual_data_imports")
    if (!hasVirtualImports) return {}

    let sql: string = PositionQueries.NON_REAL_GROUPED_BY_ENTITY_BASE

    const params: any[] = []
    const conditions: string[] = []
    if (query?.entities && query.entities.length > 0) {
      const placeholders = query.entities.map(() => "?").join(", ")
      conditions.push(`gp.entity_id IN (${placeholders})`)
      params.push(...query.entities)
    }
    // excludedEntities intentionally not applied (matches backend)

    if (conditions.length > 0) {
      sql += " WHERE " + conditions.join(" AND ")
    }

    const result = await this.client.query<any>(sql, params)
    const out: Record<string, GlobalPosition[]> = {}

    for (const row of result.rows) {
      const entityId = row.entity_id as string
      const entity: Entity = {
        id: entityId,
        name: row.entity_name,
        naturalId: row.entity_natural_id ?? null,
        type: row.entity_type,
        origin: row.entity_origin,
        iconUrl: row.icon_url ?? null,
      }

      const position: GlobalPosition = {
        id: row.id,
        entity,
        date: row.date,
        source: row.source,
        products: {},
      }

      position.products = await this._getProductPositions(
        position,
        query?.products,
      )

      const list = out[entityId] ?? []
      list.push(position)
      out[entityId] = list
    }

    return out
  }

  private async _getProductPositions(
    position: GlobalPosition,
    productsFilter?: ProductType[] | null,
  ): Promise<Partial<Record<ProductType, any>>> {
    const products: Partial<Record<ProductType, any>> = {}

    const store = async (
      type: ProductType,
      fn: (id: string) => Promise<any>,
    ) => {
      if (productsFilter && !productsFilter.includes(type)) return
      const p = await fn(position.id)
      if (p) products[type] = p
    }

    await store(ProductType.ACCOUNT, this._getAccounts.bind(this))
    await store(ProductType.CARD, this._getCards.bind(this))
    await store(ProductType.LOAN, this._getLoans.bind(this))
    await store(ProductType.STOCK_ETF, this._getStocks.bind(this))
    await store(ProductType.FUND_PORTFOLIO, this._getFundPortfolios.bind(this))
    await store(ProductType.FUND, this._getFunds.bind(this))
    await store(ProductType.FACTORING, this._getFactoring.bind(this))
    await store(ProductType.REAL_ESTATE_CF, this._getRealEstateCF.bind(this))
    await store(ProductType.DEPOSIT, this._getDeposits.bind(this))
    await store(ProductType.CROWDLENDING, this._getCrowdlending.bind(this))
    await store(ProductType.CRYPTO, this._getCrypto.bind(this))
    await store(ProductType.COMMODITY, this._getCommodities.bind(this))

    return products
  }

  // --- Helper Queries (Strict Copy) ---

  private async _getAccounts(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_ACCOUNTS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows } // Wrapping in entries to match backend structure roughly
  }

  private async _getCards(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_CARDS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getLoans(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_LOANS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null

    return {
      entries: res.rows.map(row => ({
        id: row.id,
        type: row.type,
        currency: row.currency,
        name: row.name ?? null,
        currentInstallment: Number(row.current_installment),
        interestRate: Number(row.interest_rate),
        interestType: row.interest_type ?? "FIXED",
        loanAmount: Number(row.loan_amount),
        nextPaymentDate: row.next_payment_date
          ? String(row.next_payment_date).slice(0, 10)
          : null,
        principalOutstanding: Number(row.principal_outstanding),
        principalPaid:
          row.principal_paid != null ? Number(row.principal_paid) : null,
        euriborRate: row.euribor_rate != null ? Number(row.euribor_rate) : null,
        fixedYears: row.fixed_years != null ? Number(row.fixed_years) : null,
        creation: String(row.creation).slice(0, 10),
        maturity: String(row.maturity).slice(0, 10),
        unpaid: row.unpaid != null ? Number(row.unpaid) : null,
        source: row.source,
      })),
    }
  }

  private async tableExists(name: string): Promise<boolean> {
    const res = await this.client.query<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
      [name],
    )
    return res.rows.length > 0
  }

  private async _getStocks(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_STOCKS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getFundPortfolios(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_FUND_PORTFOLIOS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getFunds(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_FUNDS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getFactoring(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_FACTORING_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getRealEstateCF(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_REAL_ESTATE_CF_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getDeposits(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_DEPOSITS_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }

  private async _getCrowdlending(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_CROWDLENDING_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    // Singleton in backend? "row = cursor.fetchone()". Yes.
    // But structure in backend: return Crowdlending object.
    return res.rows[0]
  }

  private async _getCrypto(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_CRYPTO_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows } // Simplified structure
  }

  private async _getCommodities(globalPositionId: string): Promise<any> {
    const res = await this.client.query<any>(
      PositionQueries.GET_COMMODITIES_BY_GLOBAL_POSITION_ID,
      [globalPositionId],
    )
    if (res.rows.length === 0) return null
    return { entries: res.rows }
  }
}

function aggregatePositions(positions: GlobalPosition[]): GlobalPosition {
  let aggregated: GlobalPosition | null = null
  for (const position of positions) {
    aggregated = aggregated
      ? addGlobalPositions(aggregated, position)
      : position
  }
  return aggregated as GlobalPosition
}

function addGlobalPositions(
  a: GlobalPosition,
  b: GlobalPosition,
): GlobalPosition {
  return {
    ...a,
    products: mergeProductPositions(a.products, b.products),
  }
}

function mergeProductPositions(
  a?: Record<string, any> | null,
  b?: Record<string, any> | null,
): Record<string, any> {
  const merged: Record<string, any> = { ...(a ?? {}) }

  for (const [productType, productPosition] of Object.entries(b ?? {})) {
    const current = merged[productType]
    if (!current) {
      merged[productType] = productPosition
      continue
    }

    if (
      current &&
      productPosition &&
      typeof current === "object" &&
      typeof productPosition === "object" &&
      "entries" in current &&
      "entries" in productPosition &&
      Array.isArray((current as any).entries) &&
      Array.isArray((productPosition as any).entries)
    ) {
      merged[productType] = {
        ...current,
        entries: [
          ...(current as any).entries,
          ...(productPosition as any).entries,
        ],
      }
      continue
    }

    if (
      productType === ProductType.CROWDLENDING &&
      current &&
      productPosition &&
      typeof (current as any).total === "number" &&
      typeof (productPosition as any).total === "number"
    ) {
      merged[productType] = {
        ...current,
        total: (current as any).total + (productPosition as any).total,
      }
      continue
    }

    merged[productType] = current ?? productPosition
  }

  return merged
}
