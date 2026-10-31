import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import {
  ExternalEntityConnectionModals,
  useExternalEntityConnection,
} from "@/components/ExternalEntityConnection"
import en from "@/i18n/locales/en.json"
import {
  EntityType,
  ExternalEntitySetupResponseCode,
  ExternalIntegrationStatus,
  ExternalIntegrationType,
} from "@/types"
import {
  connectExternalEntity,
  getExternalEntityCandidates,
} from "@/services/api"

const { state, app, workflow } = vi.hoisted(() => ({
  state: { integrations: [] as unknown[] },
  app: {
    fetchEntities: vi.fn(),
    showToast: vi.fn(),
    fetchExternalIntegrations: vi.fn(),
  },
  workflow: { setView: vi.fn() },
}))

vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en, locale: "en-US" }) }))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({
    ...app,
    externalIntegrations: state.integrations,
  }),
}))
vi.mock("@/context/EntityWorkflowContext", () => ({
  useEntityWorkflow: () => workflow,
}))
vi.mock("@/services/api", () => ({
  connectExternalEntity: vi.fn(),
  getExternalEntityCandidates: vi.fn(),
  completeExternalEntityConnection: vi.fn(),
  disconnectExternalEntity: vi.fn(),
  getImageUrl: vi.fn(),
}))
vi.mock("@/lib/platform", () => ({
  isNativeMobile: () => false,
  isWeb: () => false,
}))
vi.mock("@/lib/externalAuth", () => ({
  INTEGRATION_OAUTH_PARAM: "integration_oauth",
  closeExternalAuthBrowser: vi.fn(),
  openExternalAuthLink: vi.fn(),
}))
vi.mock("@/hooks/useModalBackHandler", () => ({
  useModalBackHandler: vi.fn(),
}))

const enableBanking = {
  id: "ENABLE_BANKING",
  name: "Enable Banking",
  status: ExternalIntegrationStatus.ON,
  type: ExternalIntegrationType.ENTITY_PROVIDER,
  available: true,
}

function Harness() {
  const conn = useExternalEntityConnection()
  return (
    <>
      <button onClick={conn.openAddExternalEntity}>open</button>
      <ExternalEntityConnectionModals conn={conn} />
    </>
  )
}

function bank(name: string, psuTypes: string[] | null) {
  return {
    id: `ES:${name}`,
    name,
    bic: `${name.toUpperCase().replace(/\s/g, "")}ESMM`,
    type: EntityType.FINANCIAL_INSTITUTION,
    icon: null,
    psu_types: psuTypes,
  }
}

async function openInstitution(name: string, psuTypes: string[] | null) {
  vi.mocked(getExternalEntityCandidates).mockResolvedValue({
    entities: [bank(name, psuTypes)],
  })
  render(<Harness />)
  fireEvent.click(screen.getByRole("button", { name: "open" }))
  fireEvent.click(screen.getByText("ES"))
  fireEvent.click(await screen.findByText(name))
}

describe("ExternalEntityConnection PSU type", () => {
  beforeEach(() => {
    vi.clearAllMocks()
    state.integrations = [enableBanking]
    vi.mocked(connectExternalEntity).mockResolvedValue({
      code: ExternalEntitySetupResponseCode.ALREADY_LINKED,
    })
  })

  afterEach(() => {
    cleanup()
  })

  it("expands a bank that lists both types and connects with the chosen type", async () => {
    await openInstitution("Dual Bank", ["personal", "business"])

    expect(
      screen.getByRole("group", { name: en.entities.psuTypeTitle }),
    ).toBeInTheDocument()
    fireEvent.click(
      screen.getByRole("button", { name: en.entities.psuTypeBusiness }),
    )

    await waitFor(() =>
      expect(screen.getAllByText(en.entities.psuTypeBusiness)).toHaveLength(1),
    )
    expect(screen.getByText(en.entities.psuTypeTitle)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.confirm }))

    await waitFor(() =>
      expect(connectExternalEntity).toHaveBeenCalledWith(
        expect.objectContaining({
          institution_id: "ES:Dual Bank",
          provider: "ENABLE_BANKING",
          psu_type: "business",
        }),
      ),
    )
  })

  it("connects a single-type bank without expanding it", async () => {
    await openInstitution("Business Only", ["business"])

    expect(
      screen.queryByRole("group", { name: en.entities.psuTypeTitle }),
    ).not.toBeInTheDocument()
    expect(
      await screen.findByText(en.entities.psuTypeBusiness),
    ).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.confirm }))

    await waitFor(() =>
      expect(connectExternalEntity).toHaveBeenCalledWith(
        expect.objectContaining({
          institution_id: "ES:Business Only",
          psu_type: "business",
        }),
      ),
    )
  })

  it("sends no psu_type and shows no account type when the bank does not list types", async () => {
    await openInstitution("Legacy Bank", null)

    await screen.findByRole("button", { name: en.common.confirm })
    expect(screen.queryByText(en.entities.psuTypeTitle)).not.toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: en.common.confirm }))

    await waitFor(() => expect(connectExternalEntity).toHaveBeenCalledTimes(1))
    const [request] = vi.mocked(connectExternalEntity).mock.calls[0]
    expect(request).not.toHaveProperty("psu_type")
  })

  it("collapses an expanded bank when its card is clicked again", async () => {
    await openInstitution("Dual Bank", ["personal", "business"])
    expect(
      screen.getByRole("group", { name: en.entities.psuTypeTitle }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByText("Dual Bank"))

    await waitFor(() =>
      expect(
        screen.queryByText(en.entities.psuTypeBusiness),
      ).not.toBeInTheDocument(),
    )
    expect(connectExternalEntity).not.toHaveBeenCalled()
  })

  it("collapses an expanded bank when another bank is selected", async () => {
    vi.mocked(getExternalEntityCandidates).mockResolvedValue({
      entities: [
        bank("Dual Bank", ["personal", "business"]),
        bank("Business Only", ["business"]),
      ],
    })
    render(<Harness />)
    fireEvent.click(screen.getByRole("button", { name: "open" }))
    fireEvent.click(screen.getByText("ES"))
    fireEvent.click(await screen.findByText("Dual Bank"))
    expect(
      screen.getByRole("group", { name: en.entities.psuTypeTitle }),
    ).toBeInTheDocument()

    fireEvent.click(screen.getByText("Business Only"))

    await waitFor(() =>
      expect(screen.getAllByText(en.entities.psuTypeBusiness)).toHaveLength(1),
    )
    expect(screen.getByText(en.entities.psuTypeTitle)).toBeInTheDocument()
  })

  it("shows the bank logo in the Enable Banking confirmation", async () => {
    vi.mocked(getExternalEntityCandidates).mockResolvedValue({
      entities: [
        {
          ...bank("Logo Bank", ["business"]),
          icon: "https://example.com/logo.png",
        },
      ],
    })
    render(<Harness />)
    fireEvent.click(screen.getByRole("button", { name: "open" }))
    fireEvent.click(screen.getByText("ES"))
    fireEvent.click(await screen.findByText("Logo Bank"))

    await waitFor(() =>
      expect(screen.getAllByRole("img", { name: "Logo Bank" })).toHaveLength(2),
    )
  })
})
