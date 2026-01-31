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
  SavePendingFlowsRequest,
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
  InstrumentOverview,
  InstrumentsResponse,
  CryptoWalletConnectionResult,
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
} from "@/types"
import {
  EntityContributions,
  ContributionQueryRequest,
  ManualContributionsRequest,
} from "../types/contributions"
import {
  EntitiesPosition,
  PositionQueryRequest,
  UpdatePositionRequest,
} from "../types/position"
import type { Historic, HistoricQueryRequest } from "../types/historic"
import {
  TransactionQueryRequest,
  TransactionsResult,
  ManualTransactionPayload,
} from "../types/transactions"
import { handleApiError } from "@/utils/apiErrors"
import { getApiClient } from "./apiClient"
import { AppSettings } from "@/context/AppContext"
import { triggerDeferredInit } from "@/lib/mobile"

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

export async function disconnectEntity(entityId: string): Promise<void> {
  await (await getApiClient()).delete("/entities/login", { id: entityId })
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
  }

  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/transactions${queryString}`)
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
  }

  const queryString = params.toString() ? `?${params.toString()}` : ""
  return (await getApiClient()).get(`/historic${queryString}`)
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
    if (error.status === 500) {
      throw new Error("Server error")
    }
    throw new Error("Signup failed")
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

export async function saveManualPositions(
  request: UpdatePositionRequest,
): Promise<void> {
  return (await getApiClient()).post("/data/manual/positions", request)
}

export async function updateQuotesManualPositions(): Promise<void> {
  return (await getApiClient()).post("/data/manual/positions/update-quotes")
}

export async function createManualTransaction(
  request: ManualTransactionPayload,
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

export async function savePendingFlows(
  request: SavePendingFlowsRequest,
): Promise<void> {
  return (await getApiClient()).post("/flows/pending", request)
}

export async function getAllPendingFlows(): Promise<PendingFlow[]> {
  return (await getApiClient()).get("/flows/pending")
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

export async function getImageUrl(imagePath: string): Promise<string> {
  return (await getApiClient()).getImageUrl(imagePath)
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
): Promise<ExternalEntityCandidates> {
  const params = new URLSearchParams({ country })
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
): Promise<void> {
  const params = new URLSearchParams({
    external_entity_id: externalEntityId,
  })
  return (await getApiClient()).get(
    `/entities/external/complete?${params.toString()}`,
  )
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
): Promise<InstrumentOverview> {
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
