export type MarketForecastPnlInterval = "1d" | "1w" | "1m" | "all"

export type MarketForecastDecimal = number | string

export interface MarketForecastPnlPoint {
  timestamp: number
  value: MarketForecastDecimal
  entity_account_id?: string | null
  wallet_address?: string | null
}

export interface MarketForecastPosition {
  entity_account_id?: string | null
  wallet_address?: string | null
  title?: string | null
  slug?: string | null
  event_slug?: string | null
  icon?: string | null
  outcome?: string | null
  condition_id?: string | null
  asset?: string | null
  size?: MarketForecastDecimal | null
  avg_price?: MarketForecastDecimal | null
  price?: MarketForecastDecimal | null
  initial_value?: MarketForecastDecimal | null
  current_value?: MarketForecastDecimal | null
  cash_pnl?: MarketForecastDecimal | null
  percent_pnl?: MarketForecastDecimal | null
  cur_price?: MarketForecastDecimal | null
  redemption_value?: MarketForecastDecimal | null
  end_date?: string | null
  created_at?: string | null
  updated_at?: string | null
  closed_at?: string | null
  realized_pnl?: MarketForecastDecimal | null
  total_bought?: MarketForecastDecimal | null
  total_sold?: MarketForecastDecimal | null
}

export interface MarketForecastAccountSummary {
  entity_account_id: string
  entity_id?: string
  account_name?: string | null
  wallet_address: string
  profile?: Record<string, unknown> | null
}

export interface MarketForecastPnlAccount extends MarketForecastAccountSummary {
  pnl_history: MarketForecastPnlPoint[]
}

export interface MarketForecastClosedPositionsAccount extends MarketForecastAccountSummary {
  closed_positions: MarketForecastPosition[]
}

export interface MarketForecastPnlResponse {
  interval?: MarketForecastPnlInterval
  accounts: MarketForecastPnlAccount[]
  pnl_history: MarketForecastPnlPoint[]
}

export interface MarketForecastClosedPositionsResponse {
  accounts: MarketForecastClosedPositionsAccount[]
  closed_positions: MarketForecastPosition[]
}
