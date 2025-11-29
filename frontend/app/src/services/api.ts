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

import { BASE_URL } from "@/env"

let apiBaseUrl = BASE_URL
let apiUrlInitialized = false
let apiUrlInitPromise: Promise<void> | null = null
let isCustomServer = false
let customServerUrl: string | null = null

const withApiVersionSegment = (url: string): string => {
  let normalized = url.trim()
  if (!normalized) {
    throw new Error("Invalid base URL")
  }
  while (normalized.endsWith("/")) {
    normalized = normalized.slice(0, -1)
  }
  if (!normalized.endsWith("/api/v1")) {
    normalized = `${normalized}/api/v1`
  }
  return normalized
}

const initializeApiUrl = async (): Promise<void> => {
  try {
    if (
      typeof window !== "undefined" &&
      window.ipcAPI &&
      window.ipcAPI.apiUrl
    ) {
      const result = await window.ipcAPI.apiUrl()
      if (result?.url) {
        apiBaseUrl = result.url
        isCustomServer = result.custom
        if (isCustomServer) {
          customServerUrl = result.url
        }
        console.log("API URL initialized from IPC:", apiBaseUrl)
      }
    }
  } catch (error) {
    console.error("Error initializing API URL:", error)
  } finally {
    apiBaseUrl = withApiVersionSegment(apiBaseUrl)
    apiUrlInitialized = true
  }
}

const ensureInitPromise = (): Promise<void> => {
  if (!apiUrlInitPromise) {
    apiUrlInitPromise = initializeApiUrl()
  }
  return apiUrlInitPromise
}

const ensureApiUrlInitialized = async (): Promise<string> => {
  if (!apiUrlInitialized) {
    await ensureInitPromise()
  }
  return apiBaseUrl
}

export const refreshApiBaseUrl = async (): Promise<void> => {
  apiBaseUrl = BASE_URL
  apiUrlInitialized = false
  apiUrlInitPromise = null
  isCustomServer = false
  customServerUrl = null
  await ensureApiUrlInitialized()
}

export interface ApiServerInfo {
  isCustomServer: boolean
  serverDisplay: string | null
}

export const getApiServerInfo = async (): Promise<ApiServerInfo> => {
  await ensureInitPromise()
  return {
    isCustomServer,
    serverDisplay: customServerUrl,
  }
}

export async function getEntities(): Promise<EntitiesResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/entities`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function loginEntity(
  request: LoginRequest,
): Promise<LoginResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/entities/login`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  // Even if the response is not OK, we want to get the error code
  const data = await response.json()

  if (!response.ok && !data.code) {
    throw new Error("Login failed")
  }

  return data
}

export async function disconnectEntity(entityId: string): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/entities/login`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ id: entityId }),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function fetchFinancialEntity(
  request: FetchRequest,
): Promise<FetchResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/fetch/financial`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  const data = await response.json()

  if (!response.ok && !data.code) {
    throw new Error("Fetch failed")
  }

  return data
}

export async function fetchCryptoEntity(
  request: FetchRequest,
): Promise<FetchResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/fetch/crypto`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  // Even if the response is not OK, we want to get the error code
  const data = await response.json()

  if (!response.ok && !data.code) {
    throw new Error("Fetch failed")
  }

  return data
}

export async function importFetch(): Promise<ImportResult> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/import/sheets`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })

  // Even if the response is not OK, we want to get the error code
  const data = await response.json()

  if (!response.ok && !data.code) {
    throw new Error("Virtual fetch failed")
  }

  return data
}

export async function updateSheets(): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/export/sheets`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export interface FileExportResult {
  blob: Blob
  filename: string | null
  contentType: string | null
}

export async function exportFile(
  request: FileExportRequest,
): Promise<FileExportResult> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/export/file`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }

  const blob = await response.blob()
  const dispositionHeader =
    response.headers.get("Content-Disposition") ??
    response.headers.get("content-disposition")

  let filename: string | null = null
  if (dispositionHeader) {
    const utfMatch = dispositionHeader.match(/filename\*=UTF-8''([^;]+)/i)
    if (utfMatch?.[1]) {
      try {
        filename = decodeURIComponent(utfMatch[1])
      } catch {
        filename = utfMatch[1]
      }
      filename = filename.replace(/^"|"$/g, "")
    } else {
      const fallbackMatch = dispositionHeader.match(/filename="?([^";]+)"?/i)
      if (fallbackMatch?.[1]) {
        filename = fallbackMatch[1]
      }
    }
  }

  return {
    blob,
    filename,
    contentType:
      response.headers.get("Content-Type") ??
      response.headers.get("content-type"),
  }
}

export async function importFile(
  request: FileImportRequest,
  file: File,
): Promise<ImportResult> {
  const baseUrl = await ensureApiUrlInitialized()
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

  const url = new URL(`${baseUrl}/data/import/file`)
  if (typeof request.preview === "boolean") {
    url.searchParams.set("preview", request.preview ? "true" : "false")
  }

  const response = await fetch(url.toString(), {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    await handleApiError(response)
  }

  return response.json()
}

// Templates
export async function getTemplates(type: TemplateType): Promise<Template[]> {
  const baseUrl = await ensureApiUrlInitialized()
  const params = new URLSearchParams({ type })
  const response = await fetch(`${baseUrl}/templates?${params.toString()}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getTemplateFields(): Promise<
  Record<string, TemplateFeatureDefinition[]>
> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/templates/fields`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function createTemplate(
  payload: TemplateCreatePayload,
): Promise<Template | null> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/templates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
  if (response.status === 204) {
    return null
  }
  return response.json()
}

export async function updateTemplate(
  payload: TemplateUpdatePayload,
): Promise<Template | null> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/templates`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
  if (response.status === 204) {
    return null
  }
  return response.json()
}

export async function deleteTemplate(id: string): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/templates/${id}`, {
    method: "DELETE",
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function getSettings() {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/settings`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function saveSettings(settings: any) {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/settings`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(settings),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

interface CheckStatusOptions {
  baseUrlOverride?: string
}

export async function checkStatus(
  options?: CheckStatusOptions,
): Promise<StatusResponse> {
  const baseUrl = options?.baseUrlOverride
    ? withApiVersionSegment(options.baseUrlOverride)
    : await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/status`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function login(
  authRequest: AuthRequest,
): Promise<{ code: AuthResultCode; message?: string }> {
  try {
    const baseUrl = await ensureApiUrlInitialized()
    const response = await fetch(`${baseUrl}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(authRequest),
    })

    if (response.status === 401) {
      return { code: AuthResultCode.INVALID_CREDENTIALS }
    } else if (response.status === 404) {
      return { code: AuthResultCode.USER_NOT_FOUND }
    } else if (response.status === 500 || response.status === 503) {
      const data = await response.json()
      return { code: AuthResultCode.UNEXPECTED_ERROR, message: data.message }
    } else if (response.status === 409) {
      return { code: AuthResultCode.SUCCESS }
    }

    if (!response.ok) {
      return { code: AuthResultCode.UNEXPECTED_ERROR }
    }

    return { code: AuthResultCode.SUCCESS }
  } catch (error) {
    console.error("Login error:", error)
    throw error
  }
}

export const changePassword = async (
  data: ChangePasswordRequest,
): Promise<void> => {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/change-password`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(data),
  })

  if (!response.ok) {
    const errorData = await response
      .json()
      .catch(() => ({ message: "Password change failed" }))
    const errorMessage =
      errorData.message || `HTTP error! status: ${response.status}`

    // Create an error with status information for better handling
    const error = new Error(errorMessage)
    ;(error as any).status = response.status
    throw error
  }
}

export async function logout(): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/logout`, {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Failed to logout")
  }
}

export async function getContributions(
  queryParams?: ContributionQueryRequest,
): Promise<EntityContributions> {
  const baseUrl = await ensureApiUrlInitialized()

  let queryString = ""
  if (queryParams) {
    const params = new URLSearchParams()
    if (queryParams.entities && queryParams.entities.length > 0) {
      queryParams.entities.forEach((entity: string) => {
        params.append("entity", entity)
      })
    }
    if (params.toString()) {
      queryString = `?${params.toString()}`
    }
  }

  const response = await fetch(`${baseUrl}/contributions${queryString}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getPositions(
  queryParams?: PositionQueryRequest,
): Promise<EntitiesPosition> {
  const baseUrl = await ensureApiUrlInitialized()

  let queryString = ""
  if (queryParams) {
    const params = new URLSearchParams()
    if (queryParams.entities && queryParams.entities.length > 0) {
      queryParams.entities.forEach((entity: string) => {
        params.append("entity", entity)
      })
    }
    if (params.toString()) {
      queryString = `?${params.toString()}`
    }
  }

  const response = await fetch(`${baseUrl}/positions${queryString}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getTransactions(
  queryParams?: TransactionQueryRequest,
): Promise<TransactionsResult> {
  const baseUrl = await ensureApiUrlInitialized()

  let queryString = ""
  if (queryParams) {
    const params = new URLSearchParams()

    if (queryParams.page) params.append("page", queryParams.page.toString())
    if (queryParams.limit) params.append("limit", queryParams.limit.toString())

    if (queryParams.entities && queryParams.entities.length > 0) {
      queryParams.entities.forEach((entity: string) => {
        params.append("entity", entity)
      })
    }

    if (queryParams.product_types && queryParams.product_types.length > 0) {
      queryParams.product_types.forEach(type => {
        params.append("product_type", type)
      })
    }

    if (queryParams.types && queryParams.types.length > 0) {
      queryParams.types.forEach(type => {
        params.append("type", type)
      })
    }

    if (queryParams.from_date) params.append("from_date", queryParams.from_date)
    if (queryParams.to_date) params.append("to_date", queryParams.to_date)
    if (queryParams.historic_entry_id) {
      params.append("historic_entry_id", queryParams.historic_entry_id)
    }

    queryString = `?${params.toString()}`
  }

  const response = await fetch(`${baseUrl}/transactions${queryString}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getHistoric(
  queryParams?: HistoricQueryRequest,
): Promise<Historic> {
  const baseUrl = await ensureApiUrlInitialized()

  let queryString = ""
  if (queryParams) {
    const params = new URLSearchParams()

    if (queryParams.entities && queryParams.entities.length > 0) {
      queryParams.entities.forEach(entity => {
        params.append("entity", entity)
      })
    }

    if (queryParams.product_types && queryParams.product_types.length > 0) {
      queryParams.product_types.forEach(type => {
        params.append("product_type", type)
      })
    }

    if (params.toString()) {
      queryString = `?${params.toString()}`
    }
  }

  const response = await fetch(`${baseUrl}/historic${queryString}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function signup(
  authRequest: AuthRequest,
): Promise<{ success: boolean }> {
  try {
    const baseUrl = await ensureApiUrlInitialized()
    const response = await fetch(`${baseUrl}/signup`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(authRequest),
    })

    if (response.status === 409) {
      return { success: false }
    }

    if (response.status === 400) {
      return { success: false }
    }

    if (response.status === 500) {
      throw new Error("Server error")
    }

    if (!response.ok) {
      throw new Error("Signup failed")
    }

    return { success: true }
  } catch (error) {
    console.error("Signup error:", error)
    throw error
  }
}

export async function getExchangeRates(): Promise<ExchangeRates> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/exchange-rates`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function saveManualContributions(
  request: ManualContributionsRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/manual/contributions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function calculateLoan(
  request: LoanCalculationRequest,
): Promise<LoanCalculationResult> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/calculation/loan`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function saveManualPositions(
  request: UpdatePositionRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/manual/positions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function updateQuotesManualPositions(): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(
    `${baseUrl}/data/manual/positions/update-quotes`,
    {
      method: "POST",
    },
  )
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function createManualTransaction(
  request: ManualTransactionPayload,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/manual/transactions`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function updateManualTransaction(
  id: string,
  request: ManualTransactionPayload,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/manual/transactions/${id}`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function deleteManualTransaction(id: string): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/data/manual/transactions/${id}`, {
    method: "DELETE",
  })
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function getForecast(
  request: ForecastRequest,
): Promise<ForecastResult> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/forecast`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function createCryptoWallet(
  request: CreateCryptoWalletRequest,
): Promise<CryptoWalletConnectionResult> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/crypto-wallet`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function updateCryptoWallet(
  request: UpdateCryptoWalletConnectionRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/crypto-wallet`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function deleteCryptoWallet(id: string): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/crypto-wallet/${id}`, {
    method: "DELETE",
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function saveCommodity(
  request: SaveCommodityRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/commodities`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function getExternalIntegrations(): Promise<ExternalIntegrations> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/integrations`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function setupIntegration(
  integrationId: string,
  payload: Record<string, string>,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/integrations/${integrationId}`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ payload }),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function disableIntegration(integrationId: string): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/integrations/${integrationId}`, {
    method: "DELETE",
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function createPeriodicFlow(
  request: CreatePeriodicFlowRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/flows/periodic`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function updatePeriodicFlow(
  request: UpdatePeriodicFlowRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/flows/periodic`, {
    method: "PUT",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function getAllPeriodicFlows(): Promise<PeriodicFlow[]> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/flows/periodic`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function deletePeriodicFlow(flowId: string): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/flows/periodic/${flowId}`, {
    method: "DELETE",
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function savePendingFlows(
  request: SavePendingFlowsRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/flows/pending`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function getAllPendingFlows(): Promise<PendingFlow[]> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/flows/pending`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getAllRealEstate(): Promise<RealEstate[]> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/real-estate`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function createRealEstate(
  request: CreateRealEstateRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()

  const formData = new FormData()
  formData.append("data", JSON.stringify(request.data))

  if (request.photo) {
    formData.append("photo", request.photo)
  }

  const response = await fetch(`${baseUrl}/real-estate`, {
    method: "POST",
    body: formData,
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function updateRealEstate(
  request: UpdateRealEstateRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()

  const formData = new FormData()
  formData.append("data", JSON.stringify(request.data))

  if (request.photo) {
    formData.append("photo", request.photo)
  }

  const response = await fetch(`${baseUrl}/real-estate`, {
    method: "PUT",
    body: formData,
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function deleteRealEstate(
  realEstateId: string,
  request: DeleteRealEstateRequest,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/real-estate/${realEstateId}`, {
    method: "DELETE",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function getImageUrl(imagePath: string): Promise<string> {
  const baseUrl = await ensureApiUrlInitialized()
  // Remove /api/v1 from the end and add the image path
  const imageBaseUrl = baseUrl.replace("/api/v1", "")
  return `${imageBaseUrl}${imagePath}`
}

// External entity endpoints
export async function getExternalEntityCandidates(
  country: string,
): Promise<ExternalEntityCandidates> {
  const baseUrl = await ensureApiUrlInitialized()
  const params = new URLSearchParams({ country })
  const response = await fetch(
    `${baseUrl}/entities/external/candidates?${params.toString()}`,
  )
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function connectExternalEntity(
  request: ConnectExternalEntityRequest,
): Promise<ExternalEntityConnectionResult> {
  const baseUrl = await ensureApiUrlInitialized()
  const locale =
    (typeof window !== "undefined" &&
      typeof localStorage !== "undefined" &&
      (localStorage.getItem("locale") || undefined)) ||
    "en-US"
  const response = await fetch(`${baseUrl}/entities/external`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      "Accept-Language": locale,
    },
    body: JSON.stringify(request),
  })
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function completeExternalEntityConnection(
  externalEntityId: string,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const params = new URLSearchParams({
    external_entity_id: externalEntityId,
  })
  const response = await fetch(
    `${baseUrl}/entities/external/complete?${params.toString()}`,
  )
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function disconnectExternalEntity(
  externalEntityId: string,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(
    `${baseUrl}/entities/external/${externalEntityId}`,
    { method: "DELETE" },
  )
  if (!response.ok) {
    await handleApiError(response)
  }
}

export async function fetchExternalEntity(
  externalEntityId: string,
): Promise<FetchResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(
    `${baseUrl}/data/fetch/external/${externalEntityId}`,
    { method: "POST" },
  )
  const data = await response.json()
  if (!response.ok && !data.code) {
    throw new Error("Fetch failed")
  }
  return data
}

export async function getInstruments(
  request: InstrumentDataRequest,
): Promise<InstrumentsResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const params = new URLSearchParams()

  params.append("type", request.type)
  if (request.isin) params.append("isin", request.isin)
  if (request.name) params.append("name", request.name)
  if (request.ticker) params.append("ticker", request.ticker)

  const response = await fetch(`${baseUrl}/instruments?${params.toString()}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getInstrumentDetails(
  request: InstrumentDataRequest,
): Promise<InstrumentOverview> {
  const baseUrl = await ensureApiUrlInitialized()
  const params = new URLSearchParams()

  params.append("type", request.type)
  if (request.isin) params.append("isin", request.isin)
  if (request.name) params.append("name", request.name)
  if (request.ticker) params.append("ticker", request.ticker)

  const response = await fetch(
    `${baseUrl}/instruments/details?${params.toString()}`,
  )
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function getMoneyEvents(
  query: MoneyEventQuery,
): Promise<MoneyEvents> {
  const baseUrl = await ensureApiUrlInitialized()
  const params = new URLSearchParams()
  params.append("from_date", query.from_date)
  params.append("to_date", query.to_date)

  const response = await fetch(`${baseUrl}/events?${params.toString()}`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}
