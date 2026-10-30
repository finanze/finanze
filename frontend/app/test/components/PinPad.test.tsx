import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react"
import { afterEach, describe, expect, it, vi } from "vitest"

import { PinPad } from "@/components/PinPad"
import { ModalRegistryProvider } from "@/context/ModalRegistryContext"
import en from "@/i18n/locales/en.json"

const mocks = vi.hoisted(() => ({
  login: vi.fn().mockResolvedValue(undefined),
  getLastSmsOtpMessage: vi.fn().mockResolvedValue("Your code is 999999"),
  addSmsOtpReceivedListener: vi.fn(),
  cancelEntityLogin: vi.fn().mockResolvedValue(undefined),
  entity: { id: "tr", name: "Trade Republic", pin: { positions: 4 } },
  credentials: { phone: "+490000000", password: "0000" },
}))

vi.mock("@/context/EntityWorkflowContext", () => ({
  useEntityWorkflow: () => ({
    selectedEntity: mocks.entity,
    pinLength: 6,
    pinConfirmationType: "AUTHENTICATOR",
    currentAction: "login",
    login: mocks.login,
    scrape: vi.fn(),
    storedCredentials: mocks.credentials,
    selectedFeatures: [],
    fetchOptions: {},
    pinError: false,
    clearPinError: vi.fn(),
    fetchingEntityState: { fetchingEntityIds: [] },
    resetState: vi.fn(),
    setView: vi.fn(),
    getPendingScrapeParams: () => undefined,
    clearPendingScrapeParams: vi.fn(),
    switchActivePinEntity: vi.fn(),
    getPendingPinEntities: () => [],
    processId: "test-process",
  }),
}))
vi.mock("@/context/AppContext", () => ({
  useAppContext: () => ({ showToast: vi.fn() }),
}))
vi.mock("@/i18n", () => ({ useI18n: () => ({ t: en }) }))
vi.mock("@/lib/mobile/smsOtp", () => ({
  getLastSmsOtpMessage: mocks.getLastSmsOtpMessage,
  addSmsOtpReceivedListener: mocks.addSmsOtpReceivedListener,
}))
vi.mock("@/lib/platform", () => ({ isIOS: () => false }))
vi.mock("@/services/api", () => ({
  cancelEntityLogin: mocks.cancelEntityLogin,
}))

describe("PinPad authenticator", () => {
  afterEach(() => {
    cleanup()
    vi.clearAllMocks()
  })

  it("accepts an authenticator code without reading or listening for SMS", async () => {
    render(
      <ModalRegistryProvider>
        <PinPad />
      </ModalRegistryProvider>,
    )

    expect(screen.getByText(en.pinpad.authenticatorHint)).toBeVisible()
    const input = screen.getByLabelText(en.pinpad.otpInputLabel)
    expect(input).toHaveAttribute("autocomplete", "off")
    expect(mocks.getLastSmsOtpMessage).not.toHaveBeenCalled()
    expect(mocks.addSmsOtpReceivedListener).not.toHaveBeenCalled()

    fireEvent.change(input, { target: { value: "003456" } })
    fireEvent.click(screen.getByRole("button", { name: en.common.submit }))

    await waitFor(() =>
      expect(mocks.login).toHaveBeenCalledWith(
        { phone: "+490000000", password: "0000" },
        "003456",
      ),
    )
  })
})
