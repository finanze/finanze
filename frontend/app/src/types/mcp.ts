export interface McpConfig {
  enabled: boolean
  read_only: boolean
  token: string | null
}

export interface UpdateMcpConfigRequest {
  enabled: boolean
  read_only: boolean
}
