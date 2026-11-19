import { TEST_PASSWORD, TEST_USER } from '../helpers/constants.js'
import {
    MOCK_CASH_ACCOUNT_NAME,
    MOCK_CASH_INFLOW_CONCEPT,
    MOCK_CASH_INTEREST_CONCEPT,
    MOCK_CONTRIBUTION_ALIAS,
    MOCK_FUND_NAME,
    MOCK_METAL_PRICES,
    MOCK_MYINVESTOR_OTP,
    MOCK_MYINVESTOR_PASSWORD,
    MOCK_MYINVESTOR_USER,
    MOCK_STOCK_NAME,
    assertNoUnexpectedPyodideErrors,
    fetchUncachedNativeRates,
    installEntityAndRatesMocks,
    startEntityAndRatesMockServer,
    type EntityAndRatesMockServer,
} from '../helpers/entity-and-rates-mock-server.js'
import {
    HEADING_XPATH,
    TEXT_XPATH,
    blurActiveElement,
    openMoreMenuPage,
    setInputValue,
    submitLoginForm,
} from '../helpers/ui.js'
import { switchToWebView } from '../helpers/webview.js'

const MYINVESTOR_CARD_TITLE = '//h3[.//span[normalize-space(.)="MyInvestor"]]'
const FEATURES_MODAL =
    '//h3[normalize-space(.)="Select features to fetch from MyInvestor"]/../..'
const FETCH_COOLDOWN_MS = 60_000

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
    const cardTitle = $(MYINVESTOR_CARD_TITLE)
    await cardTitle.waitForDisplayed({ timeout: 20_000 })
    await cardTitle.scrollIntoView({ block: 'center' })
    await cardTitle.click()
}

async function disableAutoRefresh(): Promise<void> {
    await expandBottomNav()
    await openMoreMenuPage('Settings')
    const section = $(TEXT_XPATH('Auto-refresh'))
    await section.waitForDisplayed()
    await section.scrollIntoView({ block: 'center' })
    await section.click()

    const toggle = $(
        `${TEXT_XPATH('Enable auto-refresh')}/../..//*[@role="switch"]`,
    )
    await toggle.waitForDisplayed()
    if ((await toggle.getAttribute('aria-checked')) === 'true') {
        await toggle.click()
        await expect(toggle).toHaveAttribute('aria-checked', 'false')
    }
}

async function triggerMyInvestorFetch(): Promise<void> {
    const fetchOnCard = $(
        `${MYINVESTOR_CARD_TITLE}/../..//button[normalize-space(.)="Fetch"]`,
    )
    await fetchOnCard.waitForDisplayed({ timeout: 20_000 })
    await fetchOnCard.scrollIntoView({ block: 'center' })
    await fetchOnCard.click()

    const modalFetch = $(
        `${FEATURES_MODAL}//button[normalize-space(.)="Fetch"]`,
    )
    await modalFetch.waitForClickable({ timeout: 15_000 })
    await modalFetch.click()
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
    let refetchAllowedAt: number | undefined

    before(async () => {
        server = await startEntityAndRatesMockServer()
        await signInWithEntityMocks(server.port)
        await disableAutoRefresh()
    })

    after(async () => {
        await server?.close()
    })

    afterEach(function () {
        if (this.currentTest?.state === 'failed') {
            const responses = server.requests
                .slice(-12)
                .map(
                    ({ method, path, status }) =>
                        `${method} ${path} -> ${status}`,
                )
            console.error(`Recent mock responses:\n${responses.join('\n')}`)
        }
    })

    it('loads FX exchange-rate float matrices through CapacitorHttp without worker errors', async () => {
        const from = server.requests.length
        const expectedPaths = [
            '/__mock/fx/currencies/eur.min.json',
            '/__mock/fx/currencies/usd.min.json',
            ...Object.keys(MOCK_METAL_PRICES).map(
                (symbol) => `/__mock/metals/price/${symbol}/EUR`,
            ),
        ]
        const rates = await fetchUncachedNativeRates().catch(async (error) => {
            await assertNoUnexpectedPyodideErrors()
            throw error
        })
        const requests = server.requests.slice(from)
        const missingPaths = expectedPaths.filter(
            (path) =>
                !requests.some(
                    (req) =>
                        req.path.split('?')[0] === path && req.status === 200,
                ),
        )
        expect(missingPaths).toEqual([])
        expect(rates).toEqual({
            eurToUsd: '1.08',
            usdToEur: '0.925926',
            metals: Object.fromEntries(
                Object.entries(MOCK_METAL_PRICES).map(([symbol, price]) => [
                    symbol,
                    String(price),
                ]),
            ),
        })
        await assertNoUnexpectedPyodideErrors()
    })

    it('handles MyInvestor login KO (invalid credentials) then OK with 6-digit SMS OTP', async () => {
        await clickBottomNav('Integrations')
        await $(HEADING_XPATH('Integrations')).waitForDisplayed({
            timeout: 20_000,
        })

        await openMyInvestorCard()
        await $(
            '//h3[.//span[normalize-space(.)="Enter credentials for MyInvestor"]]',
        ).waitForDisplayed({ timeout: 10_000 })

        await setInputValue('#user', MOCK_MYINVESTOR_USER)
        await setInputValue('#password', 'WrongPassword999!')
        await clickButtonByText('Submit')

        await waitForDisplayedText(
            'Invalid credentials for MyInvestor',
            25_000,
        )
        await assertNoUnexpectedPyodideErrors()

        await setInputValue('#user', MOCK_MYINVESTOR_USER)
        await setInputValue('#password', MOCK_MYINVESTOR_PASSWORD)
        await clickButtonByText('Submit')

        await $(
            '//h3[normalize-space(.)="Enter 6-digit code for MyInvestor"]',
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
        refetchAllowedAt = Date.now() + FETCH_COOLDOWN_MS
        await $(FEATURES_MODAL).waitForDisplayed({
            reverse: true,
            timeout: 30_000,
        })

        await assertNoUnexpectedPyodideErrors()

        expect(
            server.requests.some(
                (r) =>
                    r.status === 200 &&
                    r.path.includes(
                        '/cperf-server/api/v2/securities-accounts/sec-e2e-001/orders',
                    ),
            ),
        ).toBe(true)
        expect(
            server.requests.some(
                (r) =>
                    r.status === 200 &&
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
        await $(HEADING_XPATH('My Money')).waitForDisplayed({
            timeout: 15_000,
        })
        const budgetCard = $('//h3[normalize-space(.)="Budget"]')
        await budgetCard.waitForDisplayed({ timeout: 15_000 })
        await budgetCard.scrollIntoView({ block: 'center' })
        await budgetCard.click()
        const contributions = $('[data-testid="recurring-kpi-investments"]')
        await contributions.waitForClickable({ timeout: 15_000 })
        await contributions.click()
        await waitForDisplayedText(MOCK_CONTRIBUTION_ALIAS)

        await assertNoUnexpectedPyodideErrors()
    })

    it('surfaces upstream HTTP 503 failure cleanly on re-fetch without losing persisted SQLCipher data (KO)', async () => {
        const cooldownEndsAt = refetchAllowedAt
        if (cooldownEndsAt === undefined) {
            throw new Error(
                'The initial MyInvestor fetch must succeed before testing a re-fetch',
            )
        }
        await browser.waitUntil(() => Date.now() >= cooldownEndsAt, {
            timeout: FETCH_COOLDOWN_MS + 5_000,
            interval: 500,
            timeoutMsg: 'MyInvestor re-fetch cooldown did not elapse',
        })

        server.setFailEntityFetch(true)
        try {
            await clickBottomNav('Integrations')
            await $(HEADING_XPATH('Integrations')).waitForDisplayed({
                timeout: 15_000,
            })

            await triggerMyInvestorFetch()
            await waitForDisplayedText(
                'Failed to fetch data from MyInvestor',
                30_000,
            )
            const cancel = $(
                `${FEATURES_MODAL}//button[normalize-space(.)="Cancel"]`,
            )
            await cancel.waitForClickable({ timeout: 15_000 })
            await cancel.click()
            expect(
                server.requests.some(
                    (req) =>
                        req.target === 'myinvestor-api' && req.status === 503,
                ),
            ).toBe(true)
            await assertNoUnexpectedPyodideErrors([
                /(?:^|\n)httpx\.HTTPStatusError: Server error '503 [^']+' for url 'https:\/\/api\.myinvestor\.es\/[^'\n]+'(?:\nFor more information check: [^\n]+)?\s*$/,
                /myinvestor_client:\d+ \| Error Response Body:\{"status":\{(?=[^}\n]*"code":"UPSTREAM_UNAVAILABLE")(?=[^}\n]*"message":"Simulated upstream failure")[^}\n]+\}\}$/,
            ])
        } finally {
            server.setFailEntityFetch(false)
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
