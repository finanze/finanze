import type {
  EntitiesResponse,
  LoginRequest,
  ScrapeRequest,
  ScrapeResponse,
  LoginResponse,
  ExportRequest,
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

let apiBaseUrl = "http://localhost:8080"
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
    throw new Error("Failed to fetch entities")
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
    throw new Error("Failed to disconnect entity")
  }
}

export async function scrapeEntity(
  request: ScrapeRequest,
): Promise<ScrapeResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/scrape`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(request),
  })

  // Even if the response is not OK, we want to get the error code
  const data = await response.json()

  if (!response.ok && !data.code) {
    throw new Error("Scrape failed")
  }

  return data
}

export async function virtualScrape(): Promise<ScrapeResponse> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/scrape/virtual`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
  })

  // Even if the response is not OK, we want to get the error code
  const data = await response.json()

  if (!response.ok && !data.code) {
    throw new Error("Virtual scrape failed")
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
    throw new Error("Failed to update sheets")
  }
}

export async function getSettings() {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/settings`)
  if (!response.ok) {
    throw new Error("Failed to fetch settings")
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
    throw new Error("Failed to save settings")
  }
}

// New login endpoints
export async function checkLoginStatus(): Promise<{
  status: "LOCKED" | "UNLOCKED"
}> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/login`)
  if (!response.ok) {
    throw new Error("Failed to check login status")
  }
  return response.json()
}

export async function login(password: string): Promise<{ success: boolean }> {
  try {
    const baseUrl = await ensureApiUrlInitialized()
    const response = await fetch(`${baseUrl}/login`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({ password }),
    })

    if (response.status === 401) {
      return { success: false }
    }

    if (response.status === 500) {
      throw new Error("Server error")
    }

    if (!response.ok) {
      throw new Error("Login failed")
    }

    return { success: true }
  } catch (error) {
    console.error("Login error:", error)
    throw error
  }
}

export async function logout(): Promise<void> {
  const baseUrl = await ensureApiUrlInitialized()
  const response = await fetch(`${baseUrl}/logout`, {
    method: "POST",
  })

  if (!response.ok) {
    throw new Error("Logout failed")
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
    throw new Error("Failed to fetch contributions")
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
    throw new Error("Failed to fetch positions")
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
    throw new Error("Failed to fetch transactions")
  }
  return response.json()
}
