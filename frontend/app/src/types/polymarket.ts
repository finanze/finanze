export type PolymarketPnlInterval = "1d" | "1w" | "1m" | "all"

export interface PolymarketPnlPoint {
  t: number
  p: number
  entity_account_id?: string | null
  wallet_address?: string | null
}

export interface PolymarketBetPosition {
  entity_account_id?: string | null
  wallet_address?: string | null
  title?: string | null
  slug?: string | null
  eventSlug?: string | null
  icon?: string | null
  outcome?: string | null
  conditionId?: string | null
  asset?: string | null
  size?: number | null
  avgPrice?: number | null
  price?: number | null
  initialValue?: number | null
  currentValue?: number | null
  cashPnl?: number | null
  percentPnl?: number | null
  curPrice?: number | null
  redemptionValue?: number | null
  endDate?: string | null
  createdAt?: string | null
  updatedAt?: string | null
  closedAt?: string | null
  realizedPnl?: number | null
  totalBought?: number | null
  totalSold?: number | null
}

export interface PolymarketBetsAccount {
  entity_account_id: string
  entity_id?: string
  account_name?: string | null
  wallet_address: string
  profile?: Record<string, unknown> | null
  open_positions: PolymarketBetPosition[]
  closed_positions: PolymarketBetPosition[]
  pnl_history: PolymarketPnlPoint[]
}

export interface PolymarketBetsResponse {
  interval?: PolymarketPnlInterval
  accounts: PolymarketBetsAccount[]
  open_positions: PolymarketBetPosition[]
  closed_positions: PolymarketBetPosition[]
  pnl_history: PolymarketPnlPoint[]
}
