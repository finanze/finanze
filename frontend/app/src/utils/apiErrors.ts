export interface ApiError {
  code: string
  message?: string
}

export class ApiErrorException extends Error {
  public code: string
  public originalError?: Error

  constructor(code: string, message?: string, originalError?: Error) {
    super(message || code)
    this.code = code
    this.originalError = originalError
    this.name = "ApiErrorException"
  }
}

export async function handleApiError(response: Response): Promise<never> {
  try {
    const data = await response.json()

    if (data.code) {
      throw new ApiErrorException(data.code, data.message)
    }
  } catch (parseError) {
    if (parseError instanceof ApiErrorException) {
      throw parseError
    }
  }

  let genericCode = "UNEXPECTED_ERROR"
  if (response.status === 409) {
    genericCode = "CONFLICT_ERROR"
  } else if (response.status === 429) {
    genericCode = "TOO_MANY_REQUESTS"
  } else if (response.status >= 500) {
    genericCode = "SERVER_ERROR"
  } else if (response.status >= 400) {
    genericCode = "CLIENT_ERROR"
  }

  throw new ApiErrorException(genericCode)
}

export async function withApiErrorHandling<T>(
  apiCall: () => Promise<Response>,
): Promise<T> {
  try {
    const response = await apiCall()

    if (!response.ok) {
      await handleApiError(response)
    }

    return await response.json()
  } catch (error) {
    if (error instanceof ApiErrorException) {
      throw error
    }

    throw new ApiErrorException(
      "NETWORK_ERROR",
      "Network error occurred",
      error as Error,
    )
  }
}
