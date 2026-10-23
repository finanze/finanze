export type McpToolCategory =
  | "positions"
  | "transactions"
  | "activity_labels"
  | "budget"
  | "crypto"
  | "real_estate"
  | "market_data"
  | "calculators"
  | "connections"

export interface McpCategoryAccess {
  read_enabled: boolean
  write_enabled: boolean
}

export type McpCategoryPreferences = Partial<
  Record<McpToolCategory, McpCategoryAccess>
>

export interface McpToolCategoryInfo {
  id: McpToolCategory
  read_count: number
  write_count: number
  read_tools: string[]
  write_tools: string[]
}

export interface McpToolCatalog {
  tool_categories: McpToolCategoryInfo[]
  essential_count: number
  essential_tools: string[]
}

export interface McpConfig {
  enabled: boolean
  read_only: boolean
  token: string | null
  category_access: McpCategoryPreferences
}

export type McpConfigResponse = McpConfig & McpToolCatalog

export interface UpdateMcpConfigRequest {
  enabled: boolean
  read_only: boolean
  category_access?: McpCategoryPreferences
}
