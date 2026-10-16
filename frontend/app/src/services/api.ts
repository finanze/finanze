import {
  EntitiesResponse,
  LoginRequest,
  FetchRequest,
  FetchResponse,
  LoginResponse,
  AuthRequest,
  ChangePasswordRequest,
  StatusResponse,
  ExchangeRates,
  CreateCryptoWalletRequest,
  UpdateCryptoWalletConnectionRequest,
  SaveCommodityRequest,
  ImportResult,
  ExternalIntegrations,
  PeriodicFlow,
  PendingFlow,
  CreatePeriodicFlowRequest,
  UpdatePeriodicFlowRequest,
  CreatePendingFlowRequest,
  UpdatePendingFlowRequest,
  SettlePendingFlowRequest,
  PendingFlowsQuery,
  PendingFlowsPage,
  FlowStatus,
  RealEstate,
  CreateRealEstateRequest,
  UpdateRealEstateRequest,
  DeleteRealEstateRequest,
  LoanCalculationRequest,
  LoanCalculationResult,
  ForecastRequest,
  ForecastResult,
  ExternalEntityCandidates,
  ConnectExternalEntityRequest,
  ExternalEntityConnectionResult,
  AuthResultCode,
  InstrumentDataRequest,
  InstrumentInfo,
  InstrumentsResponse,
  CryptoWalletConnectionResult,
  DerivedAddressesResult,
  DeriveCryptoAddressesRequest,
  TemplateType,
  Template,
  TemplateCreatePayload,
  TemplateUpdatePayload,
  TemplateFeatureDefinition,
  FileExportRequest,
  FileImportRequest,
  MoneyEvents,
  MoneyEventQuery,
  SavingsCalculationRequest,
  SavingsCalculationResult,
  EuriborHistory,
  CloudAuthRequest,
  CloudAuthResponse,
  CloudAuthData,
  FullBackupsInfo,
  BackupSyncResult,
  UploadBackupRequest,
  ImportBackupRequest,
  BackupSettings,
  GetBackupsInfoRequest,
  CryptoAssetDetails,
  AvailableCryptoAssetsResult,
  WalletAddressesResponse,
  UpdateTrackedResult,
} from "@/types"
import {
  EntityContributions,
  ContributionQueryRequest,
  ManualContributionsRequest,
} from "../types/contributions"
import type {
  MarketForecastClosedPositionsResponse,
  MarketForecastPnlResponse,
  MarketForecastPnlInterval,
} from "../types/marketForecast"
import {
  EntitiesPosition,
  PositionQueryRequest,
  UpdatePositionRequest,
} from "../types/position"
import type {
  Historic,
  HistoricQueryRequest,
  SettleManualInvestmentRequest,
  PartialAmortizeManualInvestmentRequest,
  HistoricTxDeletion,
} from "../types/historic"
import type {
  NetworthTimeline,
  NetworthTimelineQuery,
} from "../types/networthTimeline"
import type { GainsTimeline, GainsTimelineQuery } from "../types/gainsTimeline"
import {
  TransactionQueryRequest,
  TransactionsResult,
  ManualTransactionPayload,
} from "../types/transactions"
import type {
  Label,
  LabelsResponse,
  SaveLabelRequest,
  LabelingRulesResponse,
  SaveLabelingRuleRequest,
  SavedLabelingRule,
  LabelingRuleConditions,
  LabelingRulePreview,
  UpdateTransactionLabelsRequest,
  RelabelRequest,
  RelabelResult,
  ExternalLabelingProviders,
} from "../types/labeling"
import type { AIModelValidation, AITask } from "../types/ai"
import type {
  CashflowQuery,
  CashflowSummary,
  RecurringMovements,
  RecurringMovementsQuery,
  IgnoreRecurringMovementRequest,
  IgnoredRecurringMovement,
} from "../types/cashflow"
import { handleApiError } from "@/utils/apiErrors"
import { getApiClient } from "./apiClient"
import { setTelemetryContext } from "@/lib/telemetry"
import { AppSettings } from "@/context/AppContext"
import {
  triggerDeferredInit,
  isBackgroundUpdateAvailable,
  backgroundUpdateQuotes,
  backgroundUpdateLoans,
  backgroundGetNetworthTimeline,
  backgroundGetGainsTimeline,
} from "@/lib/mobile"

export interface ApiServerInfo {
  isCustomServer: boolean
  serverDisplay: string | null
  baseUrl: string
}

export const getApiServerInfo = async (): Promise<ApiServerInfo> => {
  return (await getApiClient()).getApiServerInfo()
}

export const refreshApiBaseUrl = async (): Promise<void> => {
  return (await getApiClient()).refreshApiBaseUrl()
}

export async function getEntities(): Promise<EntitiesResponse> {
  return (await getApiClient()).get("/entities")
}

export async function loginEntity(
  request: LoginRequest,
): Promise<LoginResponse> {
  try {
    return await (await getApiClient()).post("/entities/login", request)
  } catch (error: any) {
    if (error.data && error.data.code) {
      return error.data
    }
    throw error
  }
}

export async function cancelEntityLogin(entityId: string): Promise<void> {
  await (
    await getApiClient()
  ).post("/entities/login/cancel", { entity: entityId })
}

export async function disconnectEntity(entityAccountId: string): Promise<void> {
  await (await getApiClient()).delete("/entities/login", { entityAccountId })
}

export async function fetchFinancialEntity(
  request: FetchRequest,
): Promise<FetchResponse> {
  return (await getApiClient()).post("/data/fetch/financial", request)
}

export async function fetchCryptoEntity(
  request: FetchRequest,
): Promise<FetchResponse> {
  return (await getApiClient()).post("/data/fetch/crypto", request)
}

export async function importFetch(): Promise<ImportResult> {
  return (await getApiClient()).post("/data/import/sheets")
}

export async function updateSheets(): Promise<void> {
  return (await getApiClient()).post("/data/export/sheets")
}

export interface FileExportResult {
  blob: Blob
  filename: string | null
  contentType: string | null
}

export async function exportFile(
  request: FileExportRequest,
): Promise<FileExportResult> {
  return (await getApiClient()).download("/data/export/file", request)
}

export async function importFile(
  request: FileImportRequest,
  file: File,
): Promise<ImportResult> {
  const formData = new FormData()
  formData.append("file", file)
  formData.append("feature", request.feature)
  formData.append("product", request.product)
  if (request.datetime_format) {
    formData.append("datetimeFormat", request.datetime_format)
  }
  if (request.date_format) {
    formData.append("dateFormat", request.date_format)
  }
  formData.append("numberFormat", request.number_format)
  formData.append("templateId", request.templateId)
  if (
    request.templateParams &&
    Object.keys(request.templateParams).length > 0
  ) {
    formData.append("templateParams", JSON.stringify(request.templateParams))
  }

  let path = "/data/import/file"
  if (typeof request.preview === "boolean") {
    path += request.preview ? "?preview=true" : "?preview=false"
  }

  return (await getApiClient()).post(path, formData)
}

// Templates
export async function getTemplates(type: TemplateType): Promise<Template[]> {
  const params = new URLSearchParams({ type })
  return (await getApiClient()).get(`/templates?${params.toString()}`)
}

export async function getTemplateFields(): Promise<
  Record<string, TemplateFeatureDefinition[]>
> {
  return (await getApiClient()).get("/templates/fields")
}

export async function createTemplate(
  payload: TemplateCreatePayload,
): Promise<Template | null> {
  return (await getApiClient()).post("/templates", payload)
}

export async function updateTemplate(
  payload: TemplateUpdatePayload,
): Promise<Template | null> {
  return (await getApiClient()).put("/templates", payload)
}

export async function deleteTemplate(id: string): Promise<void> {
  return (await getApiClient()).delete(`/templates/${id}`)
}

export async function getSettings(): Promise<AppSettings> {
  return (await getApiClient()).get("/settings")
}

export async function saveSettings(settings: any) {
  return (await getApiClient()).post("/settings", settings)
}

interface CheckStatusOptions {
  baseUrlOverride?: string
}

export async function checkStatus(
  options?: CheckStatusOptions,
): Promise<StatusResponse> {
  if (options?.baseUrlOverride) {
    let baseUrl = options.baseUrlOverride.trim()
    while (baseUrl.endsWith("/")) {
      baseUrl = baseUrl.slice(0, -1)
    }
    if (!baseUrl.endsWith("/api/v1")) {
      baseUrl = `${baseUrl}/api/v1`
    }
    const response = await fetch(`${baseUrl}/status`)
    if (!response.ok) await handleApiError(response)
    return response.json()
  }

  const result = await (await getApiClient()).get<StatusResponse>("/status")

  setTelemetryContext({
    userId: result.user?.id,
    backendVersion: result.server?.version,
    backendOs: result.server?.platform_type,
    backendOsVersion: result.server?.platform_version,
  })

  triggerDeferredInit()

  return result
}

export async function login(
  authRequest: AuthRequest,
): Promise<{ code: AuthResultCode; message?: string }> {
  try {
    await (await getApiClient()).post("/login", authRequest)
    return { code: AuthResultCode.SUCCESS }
  } catch (error: any) {
    console.error("Login error:", error)
    if (error.status === 401) {
      return { code: AuthResultCode.INVALID_CREDENTIALS }
    } else if (error.status === 404) {
      return { code: AuthResultCode.USER_NOT_FOUND }
    } else if (error.status === 500 || error.status === 503) {
      return {
        code: AuthResultCode.UNEXPECTED_ERROR,
        message: error.data?.message || error.message,
      }
    } else if (error.status === 409) {
      return { code: AuthResultCode.SUCCESS }
    }

    // Default fallback
    return { code: AuthResultCode.UNEXPECTED_ERROR, message: error.message }
  }
}

export const changePassword = async (
  data: ChangePasswordRequest,
): Promise<void> => {
  return (await getApiClient()).post("/change-password", data)
}

export async function logout(): Promise<void> {
  return (await getApiClient()).post("/logout")
}

export async function getContributions(
  queryParams?: ContributionQueryRequest,
): Promise<EntityContributions> {
  const params = new URLSearchParams()
  if (queryParams?.entities?.length) {
    queryParams.entities.forEach(entity => params.append("entity", entity))
  }
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/contributions${queryString}`)
}

export async function getPositions(
  queryParams?: PositionQueryRequest,
): Promise<EntitiesPosition> {
  const params = new URLSearchParams()
  if (queryParams?.entities?.length) {
    queryParams.entities.forEach(entity => params.append("entity", entity))
  }
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/positions${queryString}`)
}

export async function getTransactions(
  queryParams?: TransactionQueryRequest,
): Promise<TransactionsResult> {
  const params = new URLSearchParams()

  if (queryParams) {
    if (queryParams.page) params.append("page", queryParams.page.toString())
    if (queryParams.limit) params.append("limit", queryParams.limit.toString())

    if (queryParams.entities?.length) {
      queryParams.entities.forEach(entity => params.append("entity", entity))
    }

    if (queryParams.product_types?.length) {
      queryParams.product_types.forEach(type =>
        params.append("product_type", type),
      )
    }

    if (queryParams.types?.length) {
      queryParams.types.forEach(type => params.append("type", type))
    }

    if (queryParams.from_date) params.append("from_date", queryParams.from_date)
    if (queryParams.to_date) params.append("to_date", queryParams.to_date)
    if (queryParams.historic_entry_id) {
      params.append("historic_entry_id", queryParams.historic_entry_id)
    }
    queryParams.labels?.forEach(label => params.append("label", label))
    queryParams.excluded_labels?.forEach(label =>
      params.append("exclude_label", label),
    )
    if (queryParams.unlabeled) params.append("unlabeled", "true")
    if (queryParams.search?.trim()) {
      params.append("search", queryParams.search.trim())
    }
  }

  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/transactions${queryString}`)
}

export async function getLabels(): Promise<LabelsResponse> {
  return (await getApiClient()).get("/labels")
}

export async function createLabel(request: SaveLabelRequest): Promise<Label> {
  return (await getApiClient()).post("/labels", request)
}

export async function updateLabel(
  labelId: string,
  request: SaveLabelRequest,
): Promise<void> {
  return (await getApiClient()).put(`/labels/${labelId}`, request)
}

export async function deleteLabel(labelId: string): Promise<void> {
  return (await getApiClient()).delete(`/labels/${labelId}`)
}

export async function getLabelingRules(): Promise<LabelingRulesResponse> {
  return (await getApiClient()).get("/labeling/rules")
}

export async function createLabelingRule(
  request: SaveLabelingRuleRequest,
): Promise<SavedLabelingRule> {
  return (await getApiClient()).post("/labeling/rules", request)
}

export async function updateLabelingRule(
  ruleId: string,
  request: SaveLabelingRuleRequest,
): Promise<SavedLabelingRule> {
  return (await getApiClient()).put(`/labeling/rules/${ruleId}`, request)
}

export async function deleteLabelingRule(ruleId: string): Promise<void> {
  return (await getApiClient()).delete(`/labeling/rules/${ruleId}`)
}

export async function previewLabelingRule(
  conditions: LabelingRuleConditions,
  limit = 10,
): Promise<LabelingRulePreview> {
  return (await getApiClient()).post("/labeling/rules/preview", {
    conditions,
    limit,
  })
}

export async function relabelTransactions(
  request: RelabelRequest,
): Promise<RelabelResult> {
  return (await getApiClient()).post("/labeling/relabel", request)
}

export async function updateTransactionLabels(
  txId: string,
  request: UpdateTransactionLabelsRequest,
): Promise<void> {
  return (await getApiClient()).put(`/transactions/${txId}/labels`, request)
}

export async function getExternalLabelingProviders(): Promise<ExternalLabelingProviders> {
  return (await getApiClient()).get("/labeling/external/providers")
}

export async function validateAIModel(
  provider: string,
  model: string,
  task: AITask,
  upstreamProvider?: string | null,
): Promise<AIModelValidation> {
  return (await getApiClient()).post("/ai/models/validate", {
    provider,
    model,
    task,
    upstream_provider: upstreamProvider || null,
  })
}

export async function getCashflowSummary(
  query: CashflowQuery,
): Promise<CashflowSummary> {
  const params = new URLSearchParams()
  params.append("currency", query.currency)
  params.append("from_date", query.from_date)
  params.append("to_date", query.to_date)
  if (query.granularity) params.append("granularity", query.granularity)
  query.entities?.forEach(entity => params.append("entity", entity))
  return (await getApiClient()).get(`/cashflow?${params.toString()}`)
}

export async function getRecurringMovements(
  query: RecurringMovementsQuery,
): Promise<RecurringMovements> {
  const params = new URLSearchParams()
  params.append("currency", query.currency)
  if (query.lookback_months) {
    params.append("lookback_months", query.lookback_months.toString())
  }
  if (query.type) params.append("type", query.type)
  query.entities?.forEach(entity => params.append("entity", entity))
  return (await getApiClient()).get(`/cashflow/recurring?${params.toString()}`)
}

export async function ignoreRecurringMovement(
  request: IgnoreRecurringMovementRequest,
): Promise<IgnoredRecurringMovement> {
  return (await getApiClient()).post("/cashflow/recurring/ignored", request)
}

export async function restoreRecurringMovement(
  ignoredId: string,
): Promise<void> {
  return (await getApiClient()).delete(
    `/cashflow/recurring/ignored/${ignoredId}`,
  )
}

export async function getMarketForecastPnl(
  entityAccountIds?: string[],
  interval: MarketForecastPnlInterval = "all",
): Promise<MarketForecastPnlResponse> {
  const params = new URLSearchParams()
  entityAccountIds?.forEach(entityAccountId =>
    params.append("entity_account_id", entityAccountId),
  )
  params.append("interval", interval)
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/market-forecast/pnl${queryString}`)
}

export async function getMarketForecastClosedPositions(
  entityAccountIds?: string[],
): Promise<MarketForecastClosedPositionsResponse> {
  const params = new URLSearchParams()
  entityAccountIds?.forEach(entityAccountId =>
    params.append("entity_account_id", entityAccountId),
  )
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(
    `/market-forecast/closed-positions${queryString}`,
  )
}

export async function getHistoric(
  queryParams?: HistoricQueryRequest,
): Promise<Historic> {
  const params = new URLSearchParams()

  if (queryParams) {
    if (queryParams.entities?.length) {
      queryParams.entities.forEach(entity => params.append("entity", entity))
    }
    if (queryParams.product_types?.length) {
      queryParams.product_types.forEach(type =>
        params.append("product_type", type),
      )
    }
    if (queryParams.page) params.append("page", queryParams.page.toString())
    if (queryParams.limit) params.append("limit", queryParams.limit.toString())
    if (queryParams.sort_by) params.append("sort_by", queryParams.sort_by)
    if (queryParams.sort_order)
      params.append("sort_order", queryParams.sort_order)
  }

  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/historic${queryString}`)
}

export async function settleManualInvestment(
  request: SettleManualInvestmentRequest,
): Promise<void> {
  return (await getApiClient()).post("/data/manual/investments/settle", request)
}

export async function partialAmortizeManualInvestment(
  request: PartialAmortizeManualInvestmentRequest,
): Promise<void> {
  return (await getApiClient()).post(
    "/data/manual/investments/amortize",
    request,
  )
}

export async function unsettleManualInvestment(entryId: string): Promise<void> {
  return (await getApiClient()).post(`/historic/${entryId}/unsettle`, {})
}

export async function deleteManualHistoricEntry(
  entryId: string,
  txDeletion: HistoricTxDeletion,
): Promise<void> {
  return (await getApiClient()).delete(
    `/historic/${entryId}?tx_deletion=${txDeletion}`,
  )
}

export async function signup(
  authRequest: AuthRequest,
): Promise<{ success: boolean }> {
  try {
    await (await getApiClient()).post("/signup", authRequest)
    return { success: true }
  } catch (error: any) {
    console.error("Signup error:", error)
    if (error.status === 409 || error.status === 400) {
      return { success: false }
    }
    if (error.status === 500 || error.status === 503) {
      throw new Error("Server error", { cause: error })
    }
    throw new Error("Signup failed", { cause: error })
  }
}

export async function getExchangeRates(
  cached: boolean,
): Promise<ExchangeRates> {
  return (await getApiClient()).get("/exchange-rates?cached=" + cached)
}

export async function saveManualContributions(
  request: ManualContributionsRequest,
): Promise<void> {
  return (await getApiClient()).post("/data/manual/contributions", request)
}

export async function calculateLoan(
  request: LoanCalculationRequest,
): Promise<LoanCalculationResult> {
  return (await getApiClient()).post("/calculation/loan", request)
}

export async function getEuriborRates(): Promise<EuriborHistory> {
  return (await getApiClient()).get("/rates/euribor")
}

export async function saveManualPositions(
  request: UpdatePositionRequest,
): Promise<void> {
  return (await getApiClient()).post("/data/manual/positions", request)
}

export async function updateQuotesManualPositions(): Promise<UpdateTrackedResult> {
  if (isBackgroundUpdateAvailable()) {
    return backgroundUpdateQuotes<UpdateTrackedResult>()
  }
  return (await getApiClient()).post<UpdateTrackedResult>(
    "/data/manual/positions/update-quotes",
  )
}

export async function updateTrackedLoans(): Promise<UpdateTrackedResult> {
  if (isBackgroundUpdateAvailable()) {
    return backgroundUpdateLoans<UpdateTrackedResult>()
  }
  return (await getApiClient()).post<UpdateTrackedResult>(
    "/data/manual/positions/update-loans",
  )
}

export async function createManualTransaction(
  request: ManualTransactionPayload | ManualTransactionPayload[],
): Promise<void> {
  return (await getApiClient()).post("/data/manual/transactions", request)
}

export async function updateManualTransaction(
  id: string,
  request: ManualTransactionPayload,
): Promise<void> {
  return (await getApiClient()).put(`/data/manual/transactions/${id}`, request)
}

export async function deleteManualTransaction(id: string): Promise<void> {
  return (await getApiClient()).delete(`/data/manual/transactions/${id}`)
}

export async function getForecast(
  request: ForecastRequest,
): Promise<ForecastResult> {
  return (await getApiClient()).post("/forecast", request)
}

export async function createCryptoWallet(
  request: CreateCryptoWalletRequest,
): Promise<CryptoWalletConnectionResult> {
  return (await getApiClient()).post("/crypto-wallet", request)
}

export async function updateCryptoWallet(
  request: UpdateCryptoWalletConnectionRequest,
): Promise<void> {
  return (await getApiClient()).put("/crypto-wallet", request)
}

export async function deleteCryptoWallet(id: string): Promise<void> {
  return (await getApiClient()).delete(`/crypto-wallet/${id}`)
}

export async function getCryptoWalletAddresses(
  walletId: string,
): Promise<WalletAddressesResponse> {
  return (await getApiClient()).get(
    `/crypto-wallet/addresses?wallet_id=${encodeURIComponent(walletId)}`,
  )
}

export async function deriveCryptoAddresses(
  request: DeriveCryptoAddressesRequest,
): Promise<DerivedAddressesResult> {
  const params = new URLSearchParams()
  params.set("xpub", request.xpub)
  params.set("network", request.network)
  if (request.script_type) {
    params.set("script_type", request.script_type)
  }
  if (request.range != null) {
    params.set("range", request.range.toString())
  }
  return (await getApiClient()).get(
    `/crypto-wallet/derivate?${params.toString()}`,
  )
}

export async function saveCommodity(
  request: SaveCommodityRequest,
): Promise<void> {
  return (await getApiClient()).post("/commodities", request)
}

export async function getExternalIntegrations(): Promise<ExternalIntegrations> {
  return (await getApiClient()).get("/integrations")
}

export async function setupIntegration(
  integrationId: string,
  payload: Record<string, string>,
): Promise<void> {
  return (await getApiClient()).post(`/integrations/${integrationId}`, {
    payload,
  })
}

export async function disableIntegration(integrationId: string): Promise<void> {
  return (await getApiClient()).delete(`/integrations/${integrationId}`)
}

export async function createPeriodicFlow(
  request: CreatePeriodicFlowRequest,
): Promise<void> {
  return (await getApiClient()).post("/flows/periodic", request)
}

export async function updatePeriodicFlow(
  request: UpdatePeriodicFlowRequest,
): Promise<void> {
  return (await getApiClient()).put("/flows/periodic", request)
}

export async function getAllPeriodicFlows(): Promise<PeriodicFlow[]> {
  return (await getApiClient()).get("/flows/periodic")
}

export async function deletePeriodicFlow(flowId: string): Promise<void> {
  return (await getApiClient()).delete(`/flows/periodic/${flowId}`)
}

export async function createPendingFlow(
  request: CreatePendingFlowRequest,
): Promise<void> {
  return (await getApiClient()).post("/flows/pending", request)
}

export async function updatePendingFlow(
  request: UpdatePendingFlowRequest,
): Promise<void> {
  return (await getApiClient()).put("/flows/pending", request)
}

export async function deletePendingFlow(flowId: string): Promise<void> {
  return (await getApiClient()).delete(`/flows/pending/${flowId}`)
}

export async function settlePendingFlow(
  request: SettlePendingFlowRequest,
): Promise<void> {
  return (await getApiClient()).post("/flows/pending/settle", request)
}

export async function getPendingFlows(
  query: PendingFlowsQuery = {},
): Promise<PendingFlowsPage> {
  const params = new URLSearchParams()
  query.status?.forEach(s => params.append("status", s))
  if (query.flow_type) params.append("flow_type", query.flow_type)
  query.category?.forEach(c => params.append("category", c))
  if (query.sort_by) params.append("sort_by", query.sort_by)
  if (query.order) params.append("order", query.order)
  if (query.page !== undefined) params.append("page", String(query.page))
  if (query.limit !== undefined) params.append("limit", String(query.limit))
  if (query.stats) params.append("stats", "true")
  if (query.categories) params.append("categories", "true")
  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/flows/pending${queryString}`)
}

export async function getAllPendingFlows(): Promise<PendingFlow[]> {
  const page = await getPendingFlows({ status: [FlowStatus.ACTIVE] })
  return page.entries
}

export async function getAllRealEstate(): Promise<RealEstate[]> {
  return (await getApiClient()).get("/real-estate")
}

export async function createRealEstate(
  request: CreateRealEstateRequest,
): Promise<void> {
  const formData = new FormData()
  formData.append("data", JSON.stringify(request.data))

  if (request.photo) {
    formData.append("photo", request.photo)
  }

  return (await getApiClient()).post("/real-estate", formData)
}

export async function updateRealEstate(
  request: UpdateRealEstateRequest,
): Promise<void> {
  const formData = new FormData()
  formData.append("data", JSON.stringify(request.data))

  if (request.photo) {
    formData.append("photo", request.photo)
  }

  return (await getApiClient()).put("/real-estate", formData)
}

export async function deleteRealEstate(
  realEstateId: string,
  request: DeleteRealEstateRequest,
): Promise<void> {
  return (await getApiClient()).delete(`/real-estate/${realEstateId}`, request)
}

export async function getImageUrl(
  imagePath: string,
  cacheKey?: string | number,
): Promise<string> {
  return (await getApiClient()).getImageUrl(imagePath, cacheKey)
}

export async function getCryptoAssetDetails(
  providerAssetId: string,
  provider: string,
): Promise<CryptoAssetDetails> {
  const trimmedProviderAssetId = providerAssetId.trim()
  const trimmedProvider = provider.trim()

  if (!trimmedProviderAssetId) {
    throw new Error("provider_asset_id is required")
  }

  if (!trimmedProvider) {
    throw new Error("provider is required")
  }

  const params = new URLSearchParams()
  params.set("provider", trimmedProvider)

  return (await getApiClient()).get(
    `/assets/crypto/${encodeURIComponent(trimmedProviderAssetId)}?${params.toString()}`,
  )
}

interface GetCryptoAssetsQuery {
  name?: string
  symbol?: string
  page?: number
  limit?: number
}

export async function getCryptoAssets(
  query: GetCryptoAssetsQuery,
): Promise<AvailableCryptoAssetsResult> {
  const trimmedName = query.name?.trim()
  const trimmedSymbol = query.symbol?.trim()

  const hasName = Boolean(trimmedName)
  const hasSymbol = Boolean(trimmedSymbol)

  if (hasName === hasSymbol) {
    throw new Error("Provide either 'name' or 'symbol', but not both")
  }

  const params = new URLSearchParams()

  if (hasName && trimmedName) {
    params.set("name", trimmedName)
  }

  if (hasSymbol && trimmedSymbol) {
    params.set("symbol", trimmedSymbol)
  }

  if (typeof query.page === "number") {
    params.set("page", query.page.toString())
  }

  if (typeof query.limit === "number") {
    params.set("limit", query.limit.toString())
  }

  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/assets/crypto${queryString}`)
}

// External entity endpoints
export async function getExternalEntityCandidates(
  country: string,
  provider?: string | null,
): Promise<ExternalEntityCandidates> {
  const params = new URLSearchParams({ country })
  if (provider) {
    params.set("provider", provider)
  }
  return (await getApiClient()).get(
    `/entities/external/candidates?${params.toString()}`,
  )
}

export async function connectExternalEntity(
  request: ConnectExternalEntityRequest,
): Promise<ExternalEntityConnectionResult> {
  const locale =
    (typeof window !== "undefined" &&
      typeof localStorage !== "undefined" &&
      (localStorage.getItem("locale") || undefined)) ||
    "en-US"

  return (await getApiClient()).post("/entities/external", request, {
    headers: { "Accept-Language": locale },
  })
}

export async function completeExternalEntityConnection(
  externalEntityId: string,
  code?: string | null,
): Promise<void> {
  const params = new URLSearchParams({
    external_entity_id: externalEntityId,
  })
  if (code) {
    params.set("code", code)
  }
  // The endpoint responds with an HTML body (browser-redirect friendly), so
  // request it as text to avoid the JSON parser throwing on a successful call.
  await (
    await getApiClient()
  ).get(`/entities/external/complete?${params.toString()}`, {
    responseType: "text",
  })
}

export async function disconnectExternalEntity(
  externalEntityId: string,
): Promise<void> {
  return (await getApiClient()).delete(`/entities/external/${externalEntityId}`)
}

export async function fetchExternalEntity(
  externalEntityId: string,
): Promise<FetchResponse> {
  return (await getApiClient()).post(`/data/fetch/external/${externalEntityId}`)
}

export async function getInstruments(
  request: InstrumentDataRequest,
): Promise<InstrumentsResponse> {
  const params = new URLSearchParams()
  params.append("type", request.type)
  if (request.isin) params.append("isin", request.isin)
  if (request.name) params.append("name", request.name)
  if (request.ticker) params.append("ticker", request.ticker)

  return (await getApiClient()).get(`/assets/instruments?${params.toString()}`)
}

export async function getInstrumentDetails(
  request: InstrumentDataRequest,
): Promise<InstrumentInfo> {
  const params = new URLSearchParams()

  params.append("type", request.type)
  if (request.isin) params.append("isin", request.isin)
  if (request.name) params.append("name", request.name)
  if (request.ticker) params.append("ticker", request.ticker)

  return (await getApiClient()).get(
    `/assets/instruments/details?${params.toString()}`,
  )
}

export async function getMoneyEvents(
  query: MoneyEventQuery,
): Promise<MoneyEvents> {
  const params = new URLSearchParams()
  params.append("from_date", query.from_date)
  params.append("to_date", query.to_date)

  return (await getApiClient()).get(`/events?${params.toString()}`)
}

export async function getNetworthTimeline(
  query?: NetworthTimelineQuery,
): Promise<NetworthTimeline> {
  if (isBackgroundUpdateAvailable()) {
    return backgroundGetNetworthTimeline<NetworthTimeline>(query)
  }

  const params = new URLSearchParams()
  if (query?.base_currency) params.append("base_currency", query.base_currency)
  if (query?.from_date) params.append("from_date", query.from_date)
  if (query?.to_date) params.append("to_date", query.to_date)
  if (query?.no_calculation) params.append("no_calculation", "true")

  const queryString = params.toString()
  return (await getApiClient()).get(
    `/networth-timeline${queryString ? `?${queryString}` : ""}`,
  )
}

export async function getGainsTimeline(
  query: GainsTimelineQuery,
): Promise<GainsTimeline> {
  if (isBackgroundUpdateAvailable()) {
    return backgroundGetGainsTimeline<GainsTimeline>(query)
  }

  const params = new URLSearchParams()
  params.append("base_currency", query.base_currency || "EUR")
  for (const asset of query.assets) {
    if (asset.asset_keys?.length) {
      for (const assetKey of asset.asset_keys) {
        params.append("asset", `${asset.product_type}:${assetKey}`)
      }
    } else {
      params.append("product_type", asset.product_type)
    }
    for (const portfolioName of asset.portfolio_names || []) {
      params.append("portfolio", portfolioName)
    }
    for (const equityType of asset.equity_types || []) {
      params.append("equity_type", equityType)
    }
    for (const walletId of asset.wallet_ids || []) {
      params.append("wallet_id", walletId)
    }
  }
  for (const entityId of query.entities || []) {
    params.append("entity", entityId)
  }
  if (query.from_date) params.append("from_date", query.from_date)
  if (query.to_date) params.append("to_date", query.to_date)
  if (query.accrue_fixed_income) {
    params.append("accrue_fixed_income", query.accrue_fixed_income)
  }
  if (query.calculation_mode) {
    params.append("calculation_mode", query.calculation_mode)
  }

  return (await getApiClient()).get(`/gains-timeline?${params.toString()}`)
}

export async function calculateSavings(
  request: SavingsCalculationRequest,
): Promise<SavingsCalculationResult> {
  return (await getApiClient()).post("/calculations/savings", request)
}

export async function cloudAuth(
  request: CloudAuthRequest,
): Promise<CloudAuthResponse> {
  return (await getApiClient()).post("/cloud/auth", request)
}

export async function getCloudAuthToken(): Promise<CloudAuthData | null> {
  try {
    return await (await getApiClient()).get<CloudAuthData>("/cloud/auth")
  } catch (error: any) {
    if (error.status === 404) return null
    throw error
  }
}

export async function getBackupsInfo(
  request?: GetBackupsInfoRequest,
): Promise<FullBackupsInfo> {
  const params = new URLSearchParams()
  if (request?.only_local) {
    params.set("only_local", "true")
  }
  return (await getApiClient()).get(`/cloud/backup?${params.toString()}`)
}

export async function getBackupsInfoWithCloudAuth(
  cloudAccessToken: string,
): Promise<FullBackupsInfo> {
  return (await getApiClient()).get("/cloud/backup", {
    headers: { "Cloud-Authorization": `Bearer ${cloudAccessToken}` },
  })
}

export async function uploadBackup(
  request: UploadBackupRequest,
): Promise<BackupSyncResult> {
  return (await getApiClient()).post("/cloud/backup/upload", request)
}

export async function importBackup(
  request: ImportBackupRequest,
): Promise<BackupSyncResult> {
  return (await getApiClient()).post("/cloud/backup/import", request)
}

export async function getBackupSettings(): Promise<BackupSettings> {
  return (await getApiClient()).get("/cloud/backup/settings")
}

export async function updateBackupSettings(
  settings: BackupSettings,
): Promise<void> {
  return (await getApiClient()).post("/cloud/backup/settings", settings)
}
