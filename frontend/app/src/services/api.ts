import type {
  EntitiesResponse,
  LoginRequest,
  FetchRequest,
  FetchResponse,
  LoginResponse,
  ExportRequest,
  AuthRequest,
  ChangePasswordRequest,
  LoginStatusResponse,
  ExchangeRates,
  CreateCryptoWalletRequest,
  UpdateCryptoWalletConnectionRequest,
  SaveCommodityRequest,
  VirtualFetchResponse,
  ExternalIntegrations,
  GoogleIntegrationCredentials,
  EtherscanIntegrationData,
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
} from "@/types"
import {
  EntityContributions,
  ContributionQueryRequest,
} from "../types/contributions"
import { EntitiesPosition, PositionQueryRequest } from "../types/position"
import {
  TransactionQueryRequest,
  TransactionsResult,
} from "../types/transactions"
import { handleApiError } from "@/utils/apiErrors"

import { BASE_URL } from "@/env"

let apiBaseUrl = BASE_URL
let apiUrlInitialized = false

const apiUrlInitPromise: Promise<void> = (async () => {
  try {
    if (
      typeof window !== "undefined" &&
      window.ipcAPI &&
      window.ipcAPI.apiUrl
    ) {
      const url = await window.ipcAPI.apiUrl()
      if (url) {
        apiBaseUrl = url
        console.log("API URL initialized:", apiBaseUrl)
      }
    }
  } catch (error) {
    console.error("Error initializing API URL:", error)
  } finally {
    apiUrlInitialized = true
  }
  apiBaseUrl += "/api/v1"
})()

const ensureApiUrlInitialized = async (): Promise<string> => {
  if (!apiUrlInitialized) {
    await apiUrlInitPromise
  }
  return apiBaseUrl
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
  const response = await fetch(`${baseUrl}/fetch/financial`, {
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

export async function fetchCryptoEntity(
  request: FetchRequest,
): Promise<FetchResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/fetch/crypto`, {
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

export async function virtualFetch(): Promise<VirtualFetchResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/fetch/virtual`, {
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

export async function updateSheets(request: ExportRequest): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
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

export async function checkLoginStatus(): Promise<LoginStatusResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/login`)
  if (!response.ok) {
    await handleApiError(response)
  }
  return response.json()
}

export async function login(
  authRequest: AuthRequest,
): Promise<{ success: boolean }> {
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
      return { success: false }
    }

    if (!response.ok) {
      throw new Error("Failed to login")
    }

    return { success: true }
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
    if (
      queryParams.excluded_entities &&
      queryParams.excluded_entities.length > 0
    ) {
      queryParams.excluded_entities.forEach((entity: string) => {
        params.append("excluded_entity", entity)
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
    if (
      queryParams.excluded_entities &&
      queryParams.excluded_entities.length > 0
    ) {
      queryParams.excluded_entities.forEach((entity: string) => {
        params.append("excluded_entity", entity)
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

    if (
      queryParams.excluded_entities &&
      queryParams.excluded_entities.length > 0
    ) {
      queryParams.excluded_entities.forEach((entity: string) => {
        params.append("excluded_entity", entity)
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

    queryString = `?${params.toString()}`
  }

  const response = await fetch(`${baseUrl}/transactions${queryString}`)
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

export async function createCryptoWallet(
  request: CreateCryptoWalletRequest,
): Promise<void> {
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

export async function setupGoogleIntegration(
  request: GoogleIntegrationCredentials,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/integrations/google`, {
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

export async function setupEtherscanIntegration(
  request: EtherscanIntegrationData,
): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/integrations/etherscan`, {
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
