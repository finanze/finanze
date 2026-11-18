import { TEST_PASSWORD, TEST_USER } from '../helpers/constants.js'
import {
    MOCK_CASH_ACCOUNT_NAME,
    MOCK_CASH_INFLOW_CONCEPT,
    MOCK_CASH_INTEREST_CONCEPT,
    MOCK_CONTRIBUTION_ALIAS,
    MOCK_FUND_NAME,
    MOCK_MYINVESTOR_OTP,
    MOCK_MYINVESTOR_PASSWORD,
    MOCK_MYINVESTOR_USER,
    MOCK_STOCK_NAME,
    assertNoUnexpectedPyodideErrors,
    drainPyodideWorkerErrors,
    installEntityAndRatesMocks,
    startEntityAndRatesMockServer,
    type EntityAndRatesMockServer,
} from '../helpers/entity-and-rates-mock-server.js'
import {
    HEADING_XPATH,
    TEXT_XPATH,
    blurActiveElement,
    openMoreMenuPage,
    selectTab,
    setInputValue,
    submitLoginForm,
    waitForText,
} from '../helpers/ui.js'
import { switchToWebView } from '../helpers/webview.js'

async function expandBottomNav(): Promise<void> {
    const collapsed = $(
        '[data-testid="floating-bottom-nav"][data-state="collapsed"] > div',
    )
    if (await collapsed.isDisplayed().catch(() => false)) {
        await collapsed.click()
    }
}

async function clickBottomNav(label: string): Promise<void> {
    await expandBottomNav()
    const btn = $(`button[aria-label="${label}"]`)
    await btn.waitForClickable({ timeout: 15_000 })
    await btn.click()
}

async function clickButtonByText(
    label: string,
    timeout = 20_000,
): Promise<void> {
    await blurActiveElement()
    const button = $(`//button[normalize-space()="${label}"]`)
    await button.waitForDisplayed({ timeout })
    await button.scrollIntoView({ block: 'center' })
    await button.waitForEnabled({ timeout })
    await button.waitForClickable({ timeout })
    await button.click()
}

async function signInWithEntityMocks(serverPort: number): Promise<void> {
    await switchToWebView()
    const password = $('#password')
    await password.waitForDisplayed({ timeout: 90_000 })
    await installEntityAndRatesMocks(serverPort)

    if (await $('#username').isDisplayed()) {
        await setInputValue('#username', TEST_USER)
        await setInputValue('#password', TEST_PASSWORD)
        await setInputValue('#repeatPassword', TEST_PASSWORD)
    } else {
        await setInputValue('#password', TEST_PASSWORD)
    }

    await submitLoginForm(5_000)
    await browser.waitUntil(
        async () => !(await browser.getUrl()).includes('/login'),
        { timeout: 60_000, timeoutMsg: 'Still on /login after signing in' },
    )
    await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 30_000 })
}

async function openMyInvestorCard(): Promise<void> {
    const cardTitle = $(`//h3[normalize-space()="MyInvestor"]`)
    await cardTitle.waitForDisplayed({ timeout: 20_000 })
    await cardTitle.scrollIntoView({ block: 'center' })
    await cardTitle.click()
}

async function triggerMyInvestorFetch(): Promise<void> {
    const fetchOnCard = $(
        `(//h3[normalize-space()="MyInvestor"]/ancestor::div[.//button[normalize-space()="Fetch"]][1]//button[normalize-space()="Fetch"])[1]`,
    )
    if (await fetchOnCard.isDisplayed().catch(() => false)) {
        await fetchOnCard.scrollIntoView({ block: 'center' })
        await fetchOnCard.click()
    } else {
        await openMyInvestorCard()
    }

    await waitForText('Select features to fetch from MyInvestor', 15_000)

    const modalFetch = $(
        `(//div[contains(concat(" ", @class, " "), " fixed ")]//button[normalize-space()="Fetch"])[last()]`,
    )
    await modalFetch.waitForEnabled({ timeout: 10_000 })
    await modalFetch.click()
}

async function closeFeatureSelectorIfOpen(): Promise<void> {
    const cancelBtn = $(
        `(//div[contains(concat(" ", @class, " "), " fixed ")][.//*[contains(normalize-space(), "Select features to fetch")]]//button[normalize-space()="Cancel"])[last()]`,
    )
    if (await cancelBtn.isDisplayed().catch(() => false)) {
        await cancelBtn.click().catch(() => {})
    }
}

async function waitForDisplayedText(
    text: string,
    timeout = 20_000,
): Promise<void> {
    await browser.waitUntil(
        async () => {
            const matches = await $$(TEXT_XPATH(text))
            for (const match of matches) {
                if (await match.isDisplayed()) return true
            }
            return false
        },
        {
            timeout,
            timeoutMsg: `Expected "${text}" to be displayed`,
        },
    )
}

describe('Entity fetch, native HTTP/SQLite bridges, and background worker', () => {
    let server: EntityAndRatesMockServer

    before(async () => {
        server = await startEntityAndRatesMockServer()
        await signInWithEntityMocks(server.port)
    })

    after(async () => {
        await server?.close()
    })

    it('loads FX exchange-rate float matrices through CapacitorHttp without worker errors', async () => {
        await browser.waitUntil(
            async () =>
                server.requests.some((req) =>
                    req.path.includes('/currencies/eur.min.json'),
                ),
            {
                timeout: 30_000,
                timeoutMsg:
                    'Expected GetExchangeRatesImpl to fetch /currencies/eur.min.json via CapacitorHttp',
            },
        )
        await assertNoUnexpectedPyodideErrors()
    })

    it('handles MyInvestor login KO (invalid credentials) then OK with 6-digit SMS OTP', async () => {
        await clickBottomNav('Integrations')
        await $(HEADING_XPATH('Integrations')).waitForDisplayed({
            timeout: 20_000,
        })

        await openMyInvestorCard()
        await $(
            '//*[contains(normalize-space(), "Enter credentials for")]',
        ).waitForDisplayed({ timeout: 10_000 })

        await setInputValue('#user', MOCK_MYINVESTOR_USER)
        await setInputValue('#password', 'WrongPassword999!')
        await clickButtonByText('Submit')

        await $(
            '//*[contains(normalize-space(), "Invalid credentials")]',
        ).waitForDisplayed({ timeout: 25_000 })
        await assertNoUnexpectedPyodideErrors()

        await setInputValue('#user', MOCK_MYINVESTOR_USER)
        await setInputValue('#password', MOCK_MYINVESTOR_PASSWORD)
        await clickButtonByText('Submit')

        await $(
            '//*[contains(normalize-space(), "code for MyInvestor")]',
        ).waitForDisplayed({ timeout: 25_000 })

        for (const digit of MOCK_MYINVESTOR_OTP) {
            await clickButtonByText(digit, 5_000)
        }
        await clickButtonByText('Submit')

        await waitForDisplayedText(
            'Successfully logged in to MyInvestor',
            30_000,
        )
        await assertNoUnexpectedPyodideErrors()
    })

    it('fetches positions, auto-contributions, and 220+ numeric fund/stock orders via CapacitorHttp into SQLCipher', async () => {
        await clickBottomNav('Integrations')
        await $(HEADING_XPATH('Integrations')).waitForDisplayed({
            timeout: 15_000,
        })

        await triggerMyInvestorFetch()
        await waitForDisplayedText(
            'Data successfully fetched from MyInvestor',
            45_000,
        )
        await closeFeatureSelectorIfOpen()

        await assertNoUnexpectedPyodideErrors()

        expect(
            server.requests.some((r) =>
                r.path.includes(
                    '/cperf-server/api/v2/securities-accounts/sec-e2e-001/orders',
                ),
            ),
        ).toBe(true)
        expect(
            server.requests.some((r) =>
                r.path.includes('/broker/v2/stock-orders'),
            ),
        ).toBe(true)

        await clickBottomNav('Transactions')
        await $(HEADING_XPATH('Transactions')).waitForDisplayed({
            timeout: 20_000,
        })
        await waitForDisplayedText(MOCK_FUND_NAME)
        await waitForDisplayedText(MOCK_STOCK_NAME)
        await waitForDisplayedText(MOCK_CASH_INFLOW_CONCEPT)
        await waitForDisplayedText(MOCK_CASH_INTEREST_CONCEPT)

        await clickBottomNav('My Money')
        await $(HEADING_XPATH('My Money')).waitForDisplayed({ timeout: 15_000 })
        const budgetCard = $('//*[normalize-space(text())="Budget"]')
        await budgetCard.waitForDisplayed({ timeout: 10_000 })
        await budgetCard.click()
        await $(HEADING_XPATH('Budget')).waitForDisplayed({ timeout: 15_000 })
        const invTab = $(
            '//*[@role="tab"][starts-with(normalize-space(), "Investments")]',
        )
        await invTab.waitForClickable({ timeout: 10_000 })
        await invTab.click()
        await waitForDisplayedText(MOCK_CONTRIBUTION_ALIAS)

        await assertNoUnexpectedPyodideErrors()
    })

    it('surfaces upstream HTTP 503 failure cleanly on re-fetch without losing persisted SQLCipher data (KO)', async () => {
        server.setFailEntityFetch(true)
        try {
            await clickBottomNav('Integrations')
            await $(HEADING_XPATH('Integrations')).waitForDisplayed({
                timeout: 15_000,
            })

            await triggerMyInvestorFetch()
            await $(
                '//*[contains(normalize-space(), "Failed to fetch data") or contains(normalize-space(), "Something went wrong") or contains(normalize-space(), "Unexpected error")]',
            ).waitForDisplayed({ timeout: 30_000 })
            await closeFeatureSelectorIfOpen()
        } finally {
            server.setFailEntityFetch(false)
            await drainPyodideWorkerErrors()
        }

        await clickBottomNav('Transactions')
        await $(HEADING_XPATH('Transactions')).waitForDisplayed({
            timeout: 15_000,
        })
        await waitForDisplayedText(MOCK_FUND_NAME)
        await waitForDisplayedText(MOCK_STOCK_NAME)
        await assertNoUnexpectedPyodideErrors()
    })

    it('exercises background worker timeline/gains queries across shared SQLCipher and survives logout/re-login', async () => {
        await clickBottomNav('Investments')
        await $(HEADING_XPATH('My Assets')).waitForDisplayed({
            timeout: 15_000,
        })

        const bankingCard = $('//*[normalize-space(text())="Banking"]')
        await bankingCard.waitForDisplayed({ timeout: 10_000 })
        await bankingCard.click()
        await waitForDisplayedText(MOCK_CASH_ACCOUNT_NAME)

        await clickBottomNav('Investments')
        await $(HEADING_XPATH('My Assets')).waitForDisplayed({
            timeout: 15_000,
        })
        const fundsCard = $('//*[normalize-space(text())="Funds"]')
        await fundsCard.scrollIntoView({ block: 'center' })
        await fundsCard.click()
        await waitForDisplayedText(MOCK_FUND_NAME)

        await clickBottomNav('Investments')
        await $(HEADING_XPATH('My Assets')).waitForDisplayed({
            timeout: 15_000,
        })
        const stocksCard = $('//*[normalize-space(text())="Stocks & ETFs"]')
        await stocksCard.scrollIntoView({ block: 'center' })
        await stocksCard.click()
        await waitForDisplayedText(MOCK_STOCK_NAME)

        await clickBottomNav('Summary')
        await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 15_000 })
        await assertNoUnexpectedPyodideErrors()

        await expandBottomNav()
        await openMoreMenuPage('Settings')
        await clickButtonByText('Logout', 15_000)

        const password = $('#password')
        await password.waitForDisplayed({ timeout: 15_000 })
        await setInputValue('#password', TEST_PASSWORD)
        await submitLoginForm(5_000)

        await browser.waitUntil(
            async () => !(await browser.getUrl()).includes('/login'),
            { timeout: 45_000, timeoutMsg: 'Still on /login after re-login' },
        )
        await $(HEADING_XPATH('Summary')).waitForDisplayed({ timeout: 20_000 })
        await assertNoUnexpectedPyodideErrors()
    })
})
