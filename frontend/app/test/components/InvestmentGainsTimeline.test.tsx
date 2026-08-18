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

import { InvestmentGainsTimeline } from "@/components/InvestmentGainsTimeline"
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
      gainsTimeline: {
        title: "Gains",
        value: "Value",
        gain: "Gain",
        show: "Show gains",
        hide: "Hide gains",
        loading: "Loading gains history",
        noData: "No gains history available yet",
        error: "Could not load gains history",
        retry: "Retry",
        period: "Period",
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

describe("InvestmentGainsTimeline", () => {
  it("does not fetch on mobile until expanded", async () => {
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentGainsTimeline query={query} currency="EUR" />)

    expect(api.getGainsTimeline).not.toHaveBeenCalled()
    expect(screen.queryByTestId("gains-timeline-periods")).toBeNull()
    fireEvent.click(screen.getByTestId("gains-timeline-toggle"))

    await waitFor(() => {
      expect(api.getGainsTimeline).toHaveBeenCalledWith(
        expect.objectContaining({
          assets: [expect.objectContaining(query.assets[0])],
        }),
      )
    })
    expect(screen.getByTestId("gains-timeline-periods")).toBeVisible()
    expect(await screen.findByTestId("gains-timeline-chart")).toBeVisible()
  })

  it("fetches immediately on desktop", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentGainsTimeline query={query} currency="EUR" />)

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))
    expect(await screen.findByTestId("gains-timeline-chart")).toBeVisible()
  })

  it("defaults to one year and refetches for a selected period", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockResolvedValue(timeline())

    render(<InvestmentGainsTimeline query={query} currency="EUR" />)

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))
    expect(screen.getByTestId("gains-timeline-period-1Y")).toHaveAttribute(
      "aria-pressed",
      "true",
    )
    expect(api.getGainsTimeline.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        from_date: expect.stringMatching(/^\d{4}-\d{2}-\d{2}$/),
      }),
    )

    fireEvent.click(screen.getByTestId("gains-timeline-period-YTD"))

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(2))
    expect(api.getGainsTimeline.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        from_date: `${new Date().getFullYear()}-01-01`,
      }),
    )
    expect(screen.getByTestId("gains-timeline-period-YTD")).toHaveAttribute(
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
      <InvestmentGainsTimeline query={query} currency="EUR" />,
    )
    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(1))

    rerender(
      <InvestmentGainsTimeline
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

    render(<InvestmentGainsTimeline query={query} currency="EUR" />)

    expect(await screen.findByTestId("gains-timeline-empty")).toHaveTextContent(
      "No gains history available yet",
    )
  })

  it("retries after a request error", async () => {
    setDesktop(true)
    api.getGainsTimeline.mockRejectedValueOnce(new Error("offline"))
    api.getGainsTimeline.mockResolvedValueOnce(timeline())

    render(<InvestmentGainsTimeline query={query} currency="EUR" />)

    expect(await screen.findByTestId("gains-timeline-error")).toBeVisible()
    fireEvent.click(screen.getByRole("button", { name: "Retry" }))

    await waitFor(() => expect(api.getGainsTimeline).toHaveBeenCalledTimes(2))
    expect(await screen.findByTestId("gains-timeline-chart")).toBeVisible()
  })
})
