import type { HTMLAttributes, ReactNode } from "react"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { beforeEach, describe, expect, it, vi } from "vitest"

import {
  getReturnPercentage,
  InvestmentEvolutionTimeline,
} from "@/components/InvestmentEvolutionTimeline"
import { ProductType } from "@/types/position"
import type { GainsTimeline, GainsTimelineQuery } from "@/types/gainsTimeline"

const api = vi.hoisted(() => ({
  getGainsTimeline: vi.fn(),
}))

vi.mock("@/services/api", () => api)

vi.mock("@/i18n", () => ({
  useI18n: () => ({
    locale: "en-US",
    t: {
      evolutionChart: {
        title: "Evolution",
        value: "Value",
        gain: "Gain",
        twr: "TWR",
        beta: "Beta feature",
        betaNotice: "Value evolution and gains are still in beta.",
        show: "Show evolution",
        hide: "Hide evolution",
        loading: "Loading evolution",
        fullRangeHint: "The full history can take a while the first time",
        noData: "No evolution history available yet",
        error: "Could not load evolution history",
        retry: "Retry",
        period: "Period",
        dateRange: "Date range",
        from: "From",
        to: "To",
        clear: "Clear",
        ranges: {
          ALL: "All",
          "1Y": "1Y",
          YTD: "YTD",
          "1M": "1M",
        },
      },
    },
  }),
}))

vi.mock("@/context/DataDisplayModeContext", () => ({
  useDataDisplayMode: () => ({ mode: "NONE" }),
}))

// the real one is a calendar popover; a plain input keeps the test on the wiring
vi.mock("@/components/ui/DatePicker", () => ({
  DatePicker: ({
    value,
    onChange,
    placeholder,
  }: {
    value?: string
    onChange?: (value: string) => void
    placeholder?: string
  }) => (
    <input
      placeholder={placeholder}
      value={value ?? ""}
      onChange={event => onChange?.(event.target.value)}
    />
  ),
}))

type MotionDivProps = HTMLAttributes<HTMLDivElement> & {
  children?: ReactNode
  initial?: unknown
  animate?: unknown
  exit?: unknown
  transition?: unknown
}

vi.mock("framer-motion", () => ({
  AnimatePresence: ({ children }: { children?: ReactNode }) => <>{children}</>,
  motion: {
    div: ({ children, ...props }: MotionDivProps) => {
      delete props.initial
      delete props.animate
      delete props.exit
      delete props.transition
      return <div {...props}>{children}</div>
    },
  },
}))

vi.mock("recharts", () => ({
  CartesianGrid: () => null,
  Line: () => null,
  LineChart: ({
    children,
    data,
  }: {
    children?: ReactNode
    data?: unknown[]
  }) => (
    <div data-testid="recharts-line-chart" data-values={JSON.stringify(data)}>
      {children}
    </div>
  ),
  ReferenceLine: () => null,
  ResponsiveContainer: ({ children }: { children?: ReactNode }) => (
    <div>{children}</div>
  ),
  Tooltip: () => null,
  XAxis: () => null,
  YAxis: () => null,
}))

const query: GainsTimelineQuery = {
  assets: [{ product_type: ProductType.CRYPTO }],
  base_currency: "EUR",
}

function timeline(value = 100): GainsTimeline {
  return {
    currency: "EUR",
    method: "HYBRID_VALUE",
    basis: "NET_CONTRIBUTIONS",
    quality: "COMPLETE",
    basis_status: "NOT_APPLICABLE",
    xirr: null,
    annualized_xirr: null,
    opening_value: null,
    warnings: [],
    not_applicable_reasons: [],
    points: [
      {
        date: "2025-01-01",
        value,
        cost_basis: value - 10,
        net_contributions: value - 10,
        gain: 10,
        period_return: 0.1,
        index: 110,
        breakdown: {},
      },
    ],
  }
}

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (reason?: unknown) => void
  const promise = new Promise<T>((nextResolve, nextReject) => {
    resolve = nextResolve
    reject = nextReject
  })
  return { promise, resolve, reject }
}

let isDesktop = false
let mediaQuery: MediaQueryList
let listeners: Set<(event: MediaQueryListEvent) => void>

function setDesktop(nextIsDesktop: boolean) {
  isDesktop = nextIsDesktop
  Object.defineProperty(mediaQuery, "matches", {
    configurable: true,
    value: isDesktop,
  })
  act(() => {
    for (const listener of listeners) {
      listener({ matches: isDesktop } as MediaQueryListEvent)
    }
  })
}

beforeEach(() => {
  cleanup()
  vi.clearAllMocks()
  isDesktop = false
  listeners = new Set()
  const mockedMediaQuery = {
    matches: isDesktop,
    media: "(min-width: 1024px)",
    onchange: null,
    addEventListener: (
      _type: string,
      listener: (event: MediaQueryListEvent) => void,
    ) => listeners.add(listener),
    removeEventListener: (
      _type: string,
      listener: (event: MediaQueryListEvent) => void,
    ) => listeners.delete(listener),
    addListener: (listener: (event: MediaQueryListEvent) => void) =>
      listeners.add(listener),
    removeListener: (listener: (event: MediaQueryListEvent) => void) =>
      listeners.delete(listener),
    dispatchEvent: () => true,
  }
  mediaQuery = mockedMediaQuery as unknown as MediaQueryList
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    value: vi.fn(() => mediaQuery),
  })
})

describe("InvestmentEvolutionTimeline", () => {
  it("does not fetch on mobile until expanded", async () => {
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    expect(api.getGainsTimeline).not.toHaveBeenCalled()
    expect(screen.queryByTestId("evolution-timeline-periods")).toBeNull()
    fireEvent.click(screen.getByTestId("evolution-timeline-toggle"))

    await waitFor(() => {
      expect(api.getGainsTimeline).toHaveBeenCalledWith(
        expect.objectContaining({
          assets: [expect.objectContaining(query.assets[0])],
        }),
      )
    })
    expect(screen.getByTestId("evolution-timeline-periods")).toBeVisible()
    expect(await screen.findByTestId("evolution-timeline-chart")).toBeVisible()
  })

  it("fetches immediately on desktop", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId("evolution-timeline-chart")).toBeVisible()
  })

  it("defaults to one year and refetches for a selected period", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))
    expect(screen.getByTestId("evolution-timeline-period-1Y")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(api.getGainsTimeline.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        from_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      }),
    )

    fireEvent.click(screen.getByTestId("evolution-timeline-period-YTD"))

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(2))
    expect(api.getGainsTimeline.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        from_date: `${new Date().getFullYear()}-01-01`,
      }),
    )
    expect(screen.getByTestId("evolution-timeline-period-YTD")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })

  it("renders only the latest filter response", async () => {
    setDesktop(true)
    const first = deferred<GainsTimeline>()
    const second = deferred<GainsTimeline>()
    api.getGainsTimeline
      .mockReturnValueOnce(first.promise)
      .mockReturnValueOnce(second.promise)

    const { rerender } = render(
      <InvestmentEvolutionTimeline query={query} currency="EUR" />,
    )
    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))

    rerender(
      <InvestmentEvolutionTimeline
        query={{
          ...query,
          entities: ["00000000-0000-0000-0000-000000000001"],
        }}
        currency="EUR"
      />,
    )
    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(2))

    await act(async () => first.resolve(timeline(100)))
    expect(screen.queryByTestId("recharts-line-chart")).not.toBeInTheDocument()

    await act(async () => second.resolve(timeline(200)))
    await waitFor(() => {
      expect(screen.getByTestId("recharts-line-chart")).toHaveAttribute(
        "data-values",
        expect.stringContaining('"value":200'),
      )
    })
  })

  it("shows the empty state after a successful empty response", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue({ currency: "EUR", points: [] })

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    expect(
      await screen.findByTestId("evolution-timeline-empty"),
    ).toHaveTextContent("No evolution history available yet")
  })

  it("retries after a request error", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockRejectedValueOnce(new Error("offline"))
    api.getGainsTimeline.mockResolvedValueOnce(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    expect(await screen.findByTestId("evolution-timeline-error")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(2))
    expect(await screen.findByTestId("evolution-timeline-chart")).toBeVisible()
  })

  it("renders gains without any extra request", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    expect(await screen.findByText("Gain")).toBeVisible()
    expect(api.getGainsTimeline).toHaveBeenCalledTimes(1)
  })

  it("never renders the gain outside the tooltip", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    expect(await screen.findByText("Gain")).toBeVisible()
    expect(screen.queryByTestId("evolution-gain-badge")).toBeNull()
    expect(screen.queryByTestId("evolution-return-badge")).toBeNull()
  })

  it("reads the return percentage from the base-100 index", () => {
    // the index is rebased to 100 at the start of the selected range
    expect(getReturnPercentage({ index: 100 })).toBe(0)
    expect(getReturnPercentage({ index: 111.11 })).toBeCloseTo(11.11, 2)
    expect(getReturnPercentage({ index: 75 })).toBeCloseTo(-25, 2)
    expect(getReturnPercentage({ index: null })).toBeNull()
  })

  it("hides the gains for products without a cost basis", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(
      <InvestmentEvolutionTimeline
        query={query}
        currency="EUR"
        supportsGains={false}
      />,
    )

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))
    expect(screen.queryByText("Gain")).toBeNull()
  })

  it("discloses the beta notice from the title", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    expect(screen.queryByText(/still in beta/)).toBeNull()
    fireEvent.click(screen.getByTestId("evolution-timeline-beta"))

    expect(await screen.findByText(/still in beta/)).toBeVisible()
  })

  it("warns about the slow first load only while ALL is loading", async () => {
    setDesktop(true)
    let resolveTimeline: (value: GainsTimeline) => void = () => {}
    api.getGainsTimeline.mockReturnValue(
      new Promise<GainsTimeline>(resolve => {
        resolveTimeline = resolve
      }),
    )

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    // defaults to 1Y, so no hint
    expect(
      await screen.findByTestId("evolution-timeline-loading"),
    ).toBeVisible()
    expect(screen.queryByTestId("evolution-timeline-slow-hint")).toBeNull()

    fireEvent.click(screen.getByTestId("evolution-timeline-period-ALL"))

    expect(
      await screen.findByTestId("evolution-timeline-slow-hint"),
    ).toBeVisible()

    await act(async () => {
      resolveTimeline(timeline())
    })

    expect(screen.queryByTestId("evolution-timeline-slow-hint")).toBeNull()
  })

  it("queries the custom date range and clears back to the period", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentEvolutionTimeline query={query} currency="EUR" />)

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))

    fireEvent.click(screen.getByTestId("evolution-timeline-date-range"))
    fireEvent.change(await screen.findByPlaceholderText("From"), {
      target: { value: "2025-03-01" },
    })
    fireEvent.change(screen.getByPlaceholderText("To"), {
      target: { value: "2025-09-30" },
    })

    await waitFor(() =>
      expect(api.getGainsTimeline).toHaveBeenLastCalledWith(
        expect.objectContaining({
          from_date: "2025-03-01",
          to_date: "2025-09-30",
        }),
      ),
    )
    // a custom range deselects the period buttons
    expect(screen.getByTestId("evolution-timeline-period-1Y")).toHaveAttribute(
      "aria-pressed",
      "false",
    )

    fireEvent.click(screen.getByTestId("evolution-timeline-date-range-clear"))

    await waitFor(() => {
      const lastCall = api.getGainsTimeline.mock.calls.at(-1)?.[0]
      expect(lastCall?.to_date).toBeUndefined()
      expect(lastCall?.from_date).toMatch(/^\d{4}-\d{2}-\d{2}$/)
    })
    expect(screen.getByTestId("evolution-timeline-period-1Y")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
  })
})
