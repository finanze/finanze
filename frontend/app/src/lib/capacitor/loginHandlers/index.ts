import { UNICAJA_ID, promptLogin as promptUnicajaLogin } from "./unicaja"
import { MINTOS_ID, promptLogin as promptMintosLogin } from "./mintos"
import { ING_ID, promptLogin as promptIngLogin } from "./ing"
import { IBKR_ID, promptLogin as promptIbkrLogin } from "./ibkr"
import {
  TRADE_REPUBLIC_ID,
  promptLogin as promptTradeRepublicLogin,
} from "./traderepublic"
import type {
  ExternalLoginRequest,
  ExternalLoginRequestResult,
  LoginHandlerResult,
} from "./types"

type EntityLoginHandlers = {
  [key: string]: (
    request: ExternalLoginRequest,
  ) => Promise<ExternalLoginRequestResult>
}

const entityLoginHandlerRegistry: EntityLoginHandlers = {
  [UNICAJA_ID]: promptUnicajaLogin,
  [MINTOS_ID]: promptMintosLogin,
  [ING_ID]: promptIngLogin,
  [IBKR_ID]: promptIbkrLogin,
  [TRADE_REPUBLIC_ID]: promptTradeRepublicLogin,
}

type CompletionCallback = (id: string, result: LoginHandlerResult) => void
let completionCallback: CompletionCallback | null = null

export function onCompletedExternalLogin(
  callback: CompletionCallback,
): () => void {
  completionCallback = callback
  return () => {
    completionCallback = null
  }
}

export function emitCompletion(id: string, result: LoginHandlerResult) {
  // Capture callback reference synchronously, then invoke asynchronously
  // to decouple from the native plugin listener context.
  // We must capture the ref now because a useEffect cleanup could null it
  // before a setTimeout fires.
  const cb = completionCallback
  if (cb) {
    console.debug("[LoginHandlers] emitCompletion scheduled for", id)
    setTimeout(() => {
      console.debug("[LoginHandlers] emitCompletion firing for", id)
      try {
        const maybePromise = cb(id, result) as unknown
        if (
          maybePromise &&
          typeof (maybePromise as Promise<void>).catch === "function"
        ) {
          ;(maybePromise as Promise<void>).catch(err => {
            console.error("[LoginHandlers] completion callback error:", err)
          })
        }
      } catch (err) {
        console.error("[LoginHandlers] completion callback sync error:", err)
      }
    }, 0)
  } else {
    console.warn(
      "[LoginHandlers] emitCompletion: no callback registered for",
      id,
    )
  }
}

export async function promptLogin(
  id: string,
  request: ExternalLoginRequest,
): Promise<ExternalLoginRequestResult> {
  const handler = entityLoginHandlerRegistry[id]
  if (handler) {
    return await handler(request)
  }

  return { success: false }
}
