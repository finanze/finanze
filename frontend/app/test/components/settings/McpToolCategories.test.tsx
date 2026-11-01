import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
  within,
} from "@testing-library/react"
import userEvent from "@testing-library/user-event"
import { McpToolCategories } from "@/components/settings/McpToolCategories"
import { McpTab } from "@/components/settings/McpTab"
import { ModalRegistryProvider } from "@/context/ModalRegistryContext"
import { I18nProvider } from "@/i18n"
import type { McpConfig, McpToolCatalog } from "@/types/mcp"

const catalog: McpToolCatalog = {
  essential_count: 2,
  essential_tools: ["get_context", "list_entities"],
  tool_categories: [
    {
      id: "positions",
      read_count: 6,
      write_count: 10,
      read_tools: [
        "get_gains_timeline",
        "get_historic_positions",
        "get_net_worth",
        "get_net_worth_timeline",
        "get_positions",
        "list_pending_flows",
      ],
      write_tools: [
        "amortize_manual_investment",
        "delete_manual_historic_entry",
        "delete_manual_position",
        "delete_pending_flow",
        "save_commodities",
        "save_manual_position",
        "save_pending_flow",
        "settle_manual_investment",
        "settle_pending_flow",
        "unsettle_manual_investment",
      ],
    },
    {
      id: "budget",
      read_count: 3,
      write_count: 4,
      read_tools: [
        "get_contributions",
        "get_money_events",
        "list_periodic_flows",
      ],
      write_tools: [
        "delete_contribution",
        "delete_periodic_flow",
        "save_contribution",
        "save_periodic_flow",
      ],
    },
    {
      id: "market_data",
      read_count: 4,
      write_count: 0,
      read_tools: [
        "get_euribor_rates",
        "get_exchange_rates",
        "get_instrument_details",
        "search_instruments",
      ],
      write_tools: [],
    },
  ],
}
const onChange = vi.fn()
const api = vi.hoisted(() => ({
  getMcpConfig: vi.fn(),
  getApiServerInfo: vi.fn(),
  updateMcpConfig: vi.fn(),
  regenerateMcpToken: vi.fn(),
  showToast: vi.fn(),
}))

vi.mock("@/services/api", () => api)
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({ showToast: api.showToast }),
}))

function renderCategories(
  overrides: Partial<McpConfig> = {},
  isSaving = false,
) {
  return render(
    <I18nProvider>
      <McpToolCategories
        config={{
          enabled: true,
          read_only: false,
          token: "token",
          category_access: {},
          ...overrides,
        }}
        catalog={catalog}
        isSaving={isSaving}
        onChange={onChange}
      />
    </I18nProvider>,
  )
}

function expand() {
  fireEvent.click(screen.getByRole("button", { name: "Tool categories" }))
}

beforeEach(() => {
  localStorage.clear()
  onChange.mockReset()
})
afterEach(cleanup)

describe("MCP tool categories", () => {
  it("shows only raw read tool names and closes with Escape", async () => {
    const user = userEvent.setup()
    renderCategories()
    expand()
    await user.click(
      screen.getByRole("button", {
        name: "Read tools in Positions & Net Worth",
      }),
    )
    const dialog = screen.getByRole("dialog", {
      name: "Read tools in Positions & Net Worth",
    })
    expect(
      within(dialog)
        .getAllByRole("listitem")
        .map(item => item.textContent),
    ).toEqual(catalog.tool_categories[0].read_tools)
    expect(
      within(dialog).queryByText("save_manual_position"),
    ).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
    await user.keyboard("{Escape}")
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument()
  })

  it("keeps write tool names inspectable while writes are paused or disabled", async () => {
    const user = userEvent.setup()
    renderCategories({
      read_only: true,
      enabled: false,
      category_access: {
        positions: { read_enabled: false, write_enabled: false },
      },
    })
    expand()
    expect(screen.getByTestId("mcp-category-positions-write")).toBeDisabled()
    await user.click(
      screen.getByRole("button", {
        name: "Write tools in Positions & Net Worth",
      }),
    )
    const dialog = screen.getByRole("dialog", {
      name: "Write tools in Positions & Net Worth",
    })
    expect(
      within(dialog)
        .getAllByRole("listitem")
        .map(item => item.textContent),
    ).toEqual(catalog.tool_categories[0].write_tools)
    expect(within(dialog).queryByText("get_positions")).not.toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it("includes Essential names and omits write info for read-only categories", async () => {
    const user = userEvent.setup()
    renderCategories()
    expand()
    expect(
      screen.queryByRole("button", { name: "Write tools in Market Data" }),
    ).not.toBeInTheDocument()
    await user.click(
      screen.getByRole("button", { name: "Read tools in Essential" }),
    )
    const dialog = screen.getByRole("dialog", {
      name: "Read tools in Essential",
    })
    expect(
      within(dialog)
        .getAllByRole("listitem")
        .map(item => item.textContent),
    ).toEqual(["get_context", "list_entities"])
  })

  it("starts collapsed and shows the effective count", () => {
    renderCategories()
    expect(
      screen.getByRole("button", { name: "Tool categories" }),
    ).toHaveAttribute("aria-expanded", "false")
    expect(screen.queryByRole("table")).not.toBeInTheDocument()
    expect(screen.getByRole("status")).toHaveTextContent("29/29 active")
    expand()
    expect(
      screen.getByRole("button", { name: "Tool categories" }),
    ).toHaveAttribute("aria-expanded", "true")
    expect(screen.getByRole("table")).toBeVisible()
    expect(screen.getByRole("row", { name: /Essential/ })).not.toContainElement(
      screen.queryByTestId("mcp-category-essential-read"),
    )
    expect(
      screen.queryByTestId("mcp-category-market_data-write"),
    ).not.toBeInTheDocument()
    expect(screen.getByTestId("mcp-categories-reset")).toBeDisabled()
  })

  it("disabling Read disables Write in one update", () => {
    renderCategories()
    expand()
    fireEvent.click(
      screen.getByRole("switch", { name: "Read Positions & Net Worth" }),
    )
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      positions: { read_enabled: false, write_enabled: false },
    })
  })

  it("enabling Write also enables Read in one update", () => {
    renderCategories({
      category_access: {
        positions: { read_enabled: false, write_enabled: false },
      },
    })
    expand()
    fireEvent.click(
      screen.getByRole("switch", { name: "Write Positions & Net Worth" }),
    )
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      positions: { read_enabled: true, write_enabled: true },
    })
  })

  it("enabling Read alone keeps Write off", () => {
    renderCategories({
      category_access: {
        positions: { read_enabled: false, write_enabled: false },
      },
    })
    expand()
    fireEvent.click(
      screen.getByRole("switch", { name: "Read Positions & Net Worth" }),
    )
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      positions: { read_enabled: true, write_enabled: false },
    })
  })

  it("disabling Write keeps Read on", () => {
    renderCategories()
    expand()
    fireEvent.click(
      screen.getByRole("switch", { name: "Write Budget & Contributions" }),
    )
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      budget: { read_enabled: true, write_enabled: false },
    })
  })

  it("global read-only pauses writes without clearing saved choices", () => {
    renderCategories({ read_only: true })
    expand()
    const write = screen.getByRole("switch", {
      name: "Write Positions & Net Worth",
    })
    expect(write).toBeDisabled()
    expect(write).toHaveAttribute("data-state", "checked")
    expect(
      screen.getByRole("switch", { name: "Read Positions & Net Worth" }),
    ).toBeEnabled()
    expect(screen.getByRole("status")).toHaveTextContent("15/29 active")
  })

  it.each([{ enabled: false }, {}])(
    "disables conflicting changes when unavailable: %j",
    overrides => {
      renderCategories(overrides, !Object.hasOwn(overrides, "enabled"))
      expand()
      for (const control of screen.getAllByRole("switch"))
        expect(control).toBeDisabled()
      expect(screen.getByTestId("mcp-categories-reset")).toBeDisabled()
      if (overrides.enabled === false)
        expect(screen.getByRole("status")).toHaveTextContent("0/29 active")
    },
  )

  it("restores all category preferences without modifying global flags", () => {
    renderCategories({
      category_access: {
        positions: { read_enabled: false, write_enabled: false },
      },
    })
    expand()
    expect(screen.getByRole("status")).toHaveTextContent("13/29 active")
    fireEvent.click(screen.getByTestId("mcp-categories-reset"))
    expect(onChange).toHaveBeenCalledExactlyOnceWith({
      positions: { read_enabled: true, write_enabled: true },
      budget: { read_enabled: true, write_enabled: true },
      market_data: { read_enabled: true, write_enabled: true },
    })
  })
})

describe("MCP category saves", () => {
  const config: McpConfig = {
    enabled: true,
    read_only: false,
    token: "token",
    category_access: {
      positions: { read_enabled: false, write_enabled: false },
    },
  }

  beforeEach(() => {
    vi.clearAllMocks()
    api.getMcpConfig.mockResolvedValue({ ...config, ...catalog })
    api.getApiServerInfo.mockResolvedValue({ baseUrl: "http://localhost:7592" })
  })

  async function renderTab() {
    render(
      <I18nProvider>
        <ModalRegistryProvider>
          <McpTab />
        </ModalRegistryProvider>
      </I18nProvider>,
    )
    await screen.findByTestId("mcp-tool-categories")
    expand()
  }

  it("preserves saved selections and catalog counts after changing global flags", async () => {
    api.updateMcpConfig.mockResolvedValue({ ...config, read_only: true })
    await renderTab()
    fireEvent.click(screen.getByTestId("mcp-read-only"))
    await waitFor(() =>
      expect(screen.getByTestId("mcp-read-only")).toHaveAttribute(
        "data-state",
        "checked",
      ),
    )
    expect(screen.getByTestId("mcp-category-positions-read")).toHaveAttribute(
      "data-state",
      "unchecked",
    )
    expect(screen.getByTestId("mcp-tool-count")).toHaveTextContent(
      "9/29 active",
    )
    expect(api.updateMcpConfig).toHaveBeenCalledWith({
      enabled: true,
      read_only: true,
      category_access: undefined,
    })
    fireEvent.click(
      screen.getByRole("button", {
        name: "Read tools in Positions & Net Worth",
      }),
    )
    expect(
      within(
        screen.getByRole("dialog", {
          name: "Read tools in Positions & Net Worth",
        }),
      ).getByText("get_positions"),
    ).toBeVisible()
  })

  it("keeps the previous selection and shows an error when saving fails", async () => {
    api.updateMcpConfig.mockRejectedValueOnce(new Error("Save failed"))
    await renderTab()
    fireEvent.click(screen.getByTestId("mcp-category-positions-write"))
    await waitFor(() =>
      expect(api.showToast).toHaveBeenCalledWith(expect.any(String), "error"),
    )
    expect(screen.getByTestId("mcp-category-positions-read")).toHaveAttribute(
      "data-state",
      "unchecked",
    )
    expect(screen.getByTestId("mcp-category-positions-write")).toHaveAttribute(
      "data-state",
      "unchecked",
    )
    expect(screen.getByTestId("mcp-tool-count")).toHaveTextContent(
      "13/29 active",
    )
  })

  it("disables conflicting saves until the atomic update completes", async () => {
    let complete: (config: McpConfig) => void = () => {}
    api.updateMcpConfig.mockImplementationOnce(
      () =>
        new Promise<McpConfig>(resolve => {
          complete = resolve
        }),
    )
    await renderTab()
    fireEvent.click(screen.getByTestId("mcp-category-positions-write"))
    expect(api.updateMcpConfig).toHaveBeenCalledWith({
      enabled: true,
      read_only: false,
      category_access: {
        positions: { read_enabled: true, write_enabled: true },
      },
    })
    expect(screen.getByTestId("mcp-enabled")).toBeDisabled()
    expect(screen.getByTestId("mcp-regenerate-token")).toBeDisabled()
    expect(screen.getByTestId("mcp-category-budget-read")).toBeDisabled()
    await act(async () => complete({ ...config, category_access: {} }))
    expect(screen.getByTestId("mcp-category-positions-read")).toHaveAttribute(
      "data-state",
      "checked",
    )
    expect(screen.getByTestId("mcp-tool-count")).toHaveTextContent(
      "29/29 active",
    )
    expect(screen.getByTestId("mcp-enabled")).toBeEnabled()
  })
})
