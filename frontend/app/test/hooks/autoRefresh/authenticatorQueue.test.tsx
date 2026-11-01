import { act, cleanup } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

import { LoginConfirmationType } from "@/types"
import { buildEntity, resetBuilderCounters } from "./builders"
import {
  getContext,
  mockFetchFinancialEntity,
  renderContextOnly,
  resetAllMocks,
  setEntities,
} from "./setup"

beforeEach(() => {
  cleanup()
  resetAllMocks()
  resetBuilderCounters()
})

afterEach(cleanup)

describe("authenticator fetch queue", () => {
  it("preserves the active PIN and factor type when another entity needs TOTP", async () => {
    const first = buildEntity({
      id: "first",
      name: "First",
      pin: { positions: 4 },
    })
    const second = buildEntity({ id: "second", name: "Trade Republic" })
    setEntities([first, second])
    mockFetchFinancialEntity.mockImplementation(
      async (request: { entity: string; processId?: string }) => {
        if (request.entity === first.id) {
          return {
            code: "CODE_REQUESTED",
            details: { processId: "first-process" },
          }
        }
        if (!request.processId) {
          return {
            code: "CODE_REQUESTED",
            confirmationType: LoginConfirmationType.IN_APP,
            details: { processId: "second-process" },
          }
        }
        return {
          code: "CODE_REQUESTED",
          confirmationType: LoginConfirmationType.AUTHENTICATOR,
          details: { processId: "second-process", pinLength: 6 },
        }
      },
    )

    await act(async () => renderContextOnly())
    await act(async () => getContext().scrape(first, first.features))
    expect(getContext().selectedEntity?.id).toBe(first.id)
    expect(getContext().pinLength).toBe(4)

    await act(async () => getContext().scrape(second, second.features))
    expect(getContext().selectedEntity?.id).toBe(first.id)
    expect(getContext().pinConfirmationType).toBeNull()
    expect(getContext().getPendingScrapeParams(second.id)?.pinLength).toBe(6)

    act(() => getContext().switchActivePinEntity(second.id))
    expect(getContext().selectedEntity?.id).toBe(second.id)
    expect(getContext().pinConfirmationType).toBe(
      LoginConfirmationType.AUTHENTICATOR,
    )
    expect(getContext().pinLength).toBe(6)

    act(() => getContext().switchActivePinEntity(first.id))
    expect(getContext().selectedEntity?.id).toBe(first.id)
    expect(getContext().pinConfirmationType).toBeNull()
    expect(getContext().pinLength).toBe(4)
  })
})
