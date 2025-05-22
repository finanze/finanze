import { UNICAJA_ID, promptLogin as promptUnicajaLogin } from './unicaja'
import { MINTOS_ID, promptLogin as promptMintosLogin } from './mintos'

export interface ExternalLoginRequestResult {
    success: boolean
}

export interface ExternalLoginRequest {
    credentials?: Record<string, string>
}

export interface LoginHandlerResult {
    success: boolean
    credentials: Record<string, string>
}

type EntityLoginHandlers = {
    [key: string]: (
        request: ExternalLoginRequest
    ) => Promise<ExternalLoginRequestResult>
}

const entityLoginHandlerRegistry: EntityLoginHandlers = {
    [UNICAJA_ID]: promptUnicajaLogin,
    [MINTOS_ID]: promptMintosLogin,
}

export async function promptLogin(
    id: string,
    request: ExternalLoginRequest
): Promise<ExternalLoginRequestResult> {
    const handler = entityLoginHandlerRegistry[id]
    if (handler) {
        return await handler(request)
    }

    return { success: false }
}
