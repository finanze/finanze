import { describe, it, expect, beforeEach, afterEach, vi } from "vitest"
import { screen, act, cleanup, fireEvent } from "@testing-library/react"
import { BackupMode, AutoRefreshMode } from "@/types"
import { buildEntity, buildCandidate, resetBuilderCounters } from "./builders"
import {
  mockGetAutoRefreshCandidates,
  mockFetchFinancialEntity,
  setEntities,
  setBackupMode,
  setAutoRefreshSettings,
  renderDropdown,
  renderContextOnly,
  getContext,
  resetAllMocks,
} from "./setup"

beforeEach(() => {
  cleanup()
  resetAllMocks()
  resetBuilderCounters()
  vi.useFakeTimers({ shouldAdvanceTime: true })
})

afterEach(() => {
  vi.useRealTimers()
})

describe("auto-refresh pending state", () => {
  it("sets pending candidates immediately when auto-refresh is configured", async () => {
    const entity = buildEntity({ id: "e1", name: "Bank A" })
    const candidates = [buildCandidate({ id: "e1", name: "Bank A" })]

    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    const ctx = getContext()
    expect(ctx.pendingAutoRefreshCandidates).toHaveLength(1)
    expect(ctx.pendingAutoRefreshCandidates[0].entity.id).toBe("e1")
  })

  it("does not set candidates when auto-refresh is OFF", async () => {
    const entity = buildEntity({ id: "e1" })
    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.OFF })

    await act(async () => {
      renderContextOnly()
    })

    const ctx = getContext()
    expect(ctx.pendingAutoRefreshCandidates).toHaveLength(0)
  })

  it("does not set candidates when getAutoRefreshCandidates returns empty", async () => {
    const entity = buildEntity({ id: "e1" })
    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    mockGetAutoRefreshCandidates.mockReturnValue([])

    await act(async () => {
      renderContextOnly()
    })

    const ctx = getContext()
    expect(ctx.pendingAutoRefreshCandidates).toHaveLength(0)
  })
})

describe("countdown in non-AUTO backup mode", () => {
  it("starts countdown immediately and decrements each second", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    expect(getContext().autoRefreshCountdown).toBe(3)

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(getContext().autoRefreshCountdown).toBe(2)

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    expect(getContext().autoRefreshCountdown).toBe(1)
  })

  it("calls scrape for all candidates when countdown reaches 0", async () => {
    const e1 = buildEntity({ id: "e1" })
    const e2 = buildEntity({ id: "e2" })
    const candidates = [
      buildCandidate({ id: "e1" }),
      buildCandidate({ id: "e2" }),
    ]
    setEntities([e1, e2])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      await new Promise(r => setTimeout(r, 0))
    })

    expect(mockFetchFinancialEntity).toHaveBeenCalledTimes(2)

    const ctx = getContext()
    expect(ctx.pendingAutoRefreshCandidates).toHaveLength(0)
    expect(ctx.autoRefreshCountdown).toBeNull()
  })
})

describe("countdown in AUTO backup mode", () => {
  it("sets pending candidates but countdown stays null until sync completes", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.AUTO)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    const ctx = getContext()
    expect(ctx.pendingAutoRefreshCandidates).toHaveLength(1)
    expect(ctx.autoRefreshCountdown).toBeNull()
  })

  it("starts countdown after backup-auto-sync-complete event", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.AUTO)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    expect(getContext().autoRefreshCountdown).toBeNull()

    await act(async () => {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
    })

    expect(getContext().autoRefreshCountdown).toBe(3)
  })

  it("scrapes after sync event + countdown expires", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.AUTO)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    await act(async () => {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
    })

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      await new Promise(r => setTimeout(r, 0))
    })

    expect(mockFetchFinancialEntity).toHaveBeenCalledTimes(1)
  })
})

describe("cancel all auto-refresh", () => {
  it("clears all candidates and stops countdown", async () => {
    const candidates = [
      buildCandidate({ id: "e1" }),
      buildCandidate({ id: "e2" }),
    ]
    setEntities([buildEntity({ id: "e1" }), buildEntity({ id: "e2" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    expect(getContext().pendingAutoRefreshCandidates).toHaveLength(2)
    expect(getContext().autoRefreshCountdown).toBe(3)

    await act(async () => {
      getContext().cancelAutoRefresh()
    })

    expect(getContext().pendingAutoRefreshCandidates).toHaveLength(0)
    expect(getContext().autoRefreshCountdown).toBeNull()
  })

  it("prevents scrape calls after cancel all", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })

    await act(async () => {
      getContext().cancelAutoRefresh()
    })

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(mockFetchFinancialEntity).not.toHaveBeenCalled()
  })

  it("prevents scrape when cancelled during backup wait (AUTO mode)", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.AUTO)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    expect(getContext().autoRefreshCountdown).toBeNull()

    await act(async () => {
      getContext().cancelAutoRefresh()
    })

    await act(async () => {
      window.dispatchEvent(
        new CustomEvent("backup-auto-sync-complete", {
          detail: { hadTransfer: false },
        }),
      )
    })

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(mockFetchFinancialEntity).not.toHaveBeenCalled()
    expect(getContext().pendingAutoRefreshCandidates).toHaveLength(0)
  })
})

describe("cancel individual entity", () => {
  it("removes only the specified entity from candidates", async () => {
    const candidates = [
      buildCandidate({ id: "e1", name: "Bank A" }),
      buildCandidate({ id: "e2", name: "Bank B" }),
    ]
    setEntities([
      buildEntity({ id: "e1", name: "Bank A" }),
      buildEntity({ id: "e2", name: "Bank B" }),
    ])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    expect(getContext().pendingAutoRefreshCandidates).toHaveLength(2)

    await act(async () => {
      getContext().cancelAutoRefresh("e1")
    })

    const remaining = getContext().pendingAutoRefreshCandidates
    expect(remaining).toHaveLength(1)
    expect(remaining[0].entity.id).toBe("e2")
    expect(getContext().autoRefreshCountdown).not.toBeNull()
  })

  it("scrapes only remaining entities when countdown expires after individual cancel", async () => {
    const candidates = [
      buildCandidate({ id: "e1" }),
      buildCandidate({ id: "e2" }),
    ]
    setEntities([buildEntity({ id: "e1" }), buildEntity({ id: "e2" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    await act(async () => {
      getContext().cancelAutoRefresh("e1")
    })

    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      vi.advanceTimersByTime(1000)
    })
    await act(async () => {
      await new Promise(r => setTimeout(r, 0))
    })

    expect(mockFetchFinancialEntity).toHaveBeenCalledTimes(1)

    const callArgs = mockFetchFinancialEntity.mock.calls[0][0] as any
    expect(callArgs.entity).toBe("e2")
  })

  it("acts as cancel-all when last entity is removed", async () => {
    const candidates = [buildCandidate({ id: "e1" })]
    setEntities([buildEntity({ id: "e1" })])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderContextOnly()
    })

    await act(async () => {
      getContext().cancelAutoRefresh("e1")
    })

    expect(getContext().pendingAutoRefreshCandidates).toHaveLength(0)
    expect(getContext().autoRefreshCountdown).toBeNull()

    await act(async () => {
      vi.advanceTimersByTime(5000)
    })

    expect(mockFetchFinancialEntity).not.toHaveBeenCalled()
  })
})

describe("EntityRefreshDropdown UI", () => {
  it("shows auto-refresh banner with waiting text when countdown is null (AUTO mode)", async () => {
    const entity = buildEntity({ id: "e1", name: "Bank A" })
    const candidates = [buildCandidate({ id: "e1", name: "Bank A" })]
    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.AUTO)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderDropdown()
    })

    const button = screen.getByRole("button", { expanded: false })
    await act(async () => {
      fireEvent.click(button)
    })

    expect(screen.getByText("About to update...")).toBeInTheDocument()
  })

  it("shows countdown text when countdown is active", async () => {
    const entity = buildEntity({ id: "e1", name: "Bank A" })
    const candidates = [buildCandidate({ id: "e1", name: "Bank A" })]
    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderDropdown()
    })

    const button = screen.getByRole("button", { expanded: false })
    await act(async () => {
      fireEvent.click(button)
    })

    expect(screen.getByText("Auto-update in 3s...")).toBeInTheDocument()
  })

  it("shows X button for pending entities instead of refresh icon", async () => {
    const entity = buildEntity({ id: "e1", name: "Bank A" })
    const candidates = [buildCandidate({ id: "e1", name: "Bank A" })]
    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderDropdown()
    })

    const button = screen.getByRole("button", { expanded: false })
    await act(async () => {
      fireEvent.click(button)
    })

    const cancelButtons = screen.getAllByLabelText("Cancel auto-update")
    expect(cancelButtons.length).toBeGreaterThanOrEqual(1)
  })

  it("hides banner after cancel all", async () => {
    const entity = buildEntity({ id: "e1", name: "Bank A" })
    const candidates = [buildCandidate({ id: "e1", name: "Bank A" })]
    setEntities([entity])
    setAutoRefreshSettings({ mode: AutoRefreshMode.NO_2FA })
    setBackupMode(BackupMode.OFF)
    mockGetAutoRefreshCandidates.mockReturnValue(candidates)

    await act(async () => {
      renderDropdown()
    })

    const toggle = screen.getByRole("button", { expanded: false })
    await act(async () => {
      fireEvent.click(toggle)
    })

    expect(screen.getByText("Auto-update in 3s...")).toBeInTheDocument()

    const cancelButtons = screen.getAllByLabelText("Cancel auto-update")
    const bannerCancel = cancelButtons[0]

    await act(async () => {
      fireEvent.click(bannerCancel)
    })

    expect(
      screen.queryByText(/Auto-update in|About to update/),
    ).not.toBeInTheDocument()
  })
})
