import { switchToWebView } from '../helpers/webview.js'
import { setInputValue, submitLoginForm } from '../helpers/ui.js'
import {
    TEST_USER,
    TEST_PASSWORD,
    TEST_NEW_PASSWORD,
    TEST_WRONG_PASSWORD,
} from '../helpers/constants.js'

const HEADING_XPATH = (text: string) =>
    `//*[self::h1 or self::h2 or self::h3 or self::h4][contains(text(),"${text}")]`

const TEXT_XPATH = (text: string) => `//*[text()="${text}"]`

const log = (msg: string, start: number) =>
    console.log(`[${((Date.now() - start) / 1000).toFixed(1)}s] ${msg}`)

async function assertLoggedInForNav(): Promise<void> {
    if ((await browser.getUrl()).includes('/login')) {
        throw new Error(
            'Skipping navigation wait: app remained on /login after an earlier test failure',
        )
    }
}

describe('Basic Setup', () => {
    before(async () => {
        const t0 = Date.now()

        await switchToWebView()
        log('switchToWebView done', t0)

        // Cold Pyodide boot is slower on CI than locally; allow headroom but
        // not so much that a genuinely stuck boot wastes minutes per retry.
        await $('#username').waitForDisplayed({ timeout: 60_000 })
        log('#username visible', t0)

        await setInputValue('#username', TEST_USER)
        await setInputValue('#password', TEST_PASSWORD, 5_000)
        await setInputValue('#repeatPassword', TEST_PASSWORD, 5_000)
        await submitLoginForm(5_000)
        log('signup submitted', t0)

        await browser.waitUntil(
            async () => {
                const url = await browser.getUrl()
                return !url.includes('/login')
            },
            {
                timeout: 60_000,
                timeoutMsg: 'URL still contains /login after signup',
            },
        )
        log('navigated away from /login', t0)

        const summary = await $(HEADING_XPATH('Summary'))
        await summary.waitForDisplayed({ timeout: 10_000 })
        log('Summary heading visible', t0)

        const moreBtn = await $('button[aria-label="More"]')
        await moreBtn.waitForDisplayed({ timeout: 5_000 })
        await moreBtn.click()

        const settingsBtn = await $('button=Settings')
        await settingsBtn.waitForDisplayed({ timeout: 5_000 })
        await settingsBtn.click()

        const settingsHeading = await $(HEADING_XPATH('Settings'))
        await settingsHeading.waitForDisplayed({ timeout: 30_000 })

        const logoutBtn = await $('button=Logout')
        await logoutBtn.waitForDisplayed({ timeout: 15_000 })
        await logoutBtn.click()

        const passwordField = await $('#password')
        await passwordField.waitForDisplayed({ timeout: 10_000 })
        log('before hook complete', t0)
    })

    it('wrong password shows invalid credentials', async () => {
        await setInputValue('#password', TEST_WRONG_PASSWORD, 5_000)
        await submitLoginForm(5_000)

        await $(TEXT_XPATH('Invalid credentials')).waitForDisplayed({
            timeout: 45_000,
        })
        expect(await browser.getUrl()).toContain('/login')
        await expect($('#password')).toBeDisplayed()
        await expect(
            $(
                TEXT_XPATH(
                    'Something went wrong, please contact the Finanze team.',
                ),
            ),
        ).not.toBeDisplayed()
    })

    it('login after logout shows dashboard', async () => {
        await expect($('#username')).not.toBeDisplayed()

        await setInputValue('#password', TEST_PASSWORD, 5_000)
        await submitLoginForm(5_000)

        await browser.waitUntil(
            async () => {
                const url = await browser.getUrl()
                return !url.includes('/login')
            },
            {
                timeout: 45_000,
                timeoutMsg: 'URL still contains /login after login',
            },
        )

        const summary = await $(HEADING_XPATH('Summary'))
        await summary.waitForDisplayed({ timeout: 10_000 })
    })

    it('change encryption key and re-login works', async () => {
        const moreBtn = await $('button[aria-label="More"]')
        await moreBtn.waitForDisplayed({ timeout: 5_000 })
        await moreBtn.click()

        const settingsBtn = await $('button=Settings')
        await settingsBtn.waitForDisplayed({ timeout: 5_000 })
        await settingsBtn.click()

        const changePasswordBtn = await $('button=Change encryption key')
        await changePasswordBtn.waitForDisplayed({ timeout: 10_000 })
        await changePasswordBtn.click()

        await setInputValue('#oldPassword', TEST_WRONG_PASSWORD, 10_000)
        await setInputValue('#password', TEST_NEW_PASSWORD, 5_000)
        await setInputValue('#repeatPassword', TEST_NEW_PASSWORD, 5_000)
        await submitLoginForm(5_000)

        await $(TEXT_XPATH('Invalid credentials')).waitForDisplayed({
            timeout: 45_000,
        })
        await expect($('#oldPassword')).toBeDisplayed()

        await setInputValue('#oldPassword', TEST_PASSWORD, 10_000)
        await setInputValue('#password', TEST_NEW_PASSWORD, 5_000)
        await setInputValue('#repeatPassword', TEST_NEW_PASSWORD, 5_000)
        await submitLoginForm(5_000)

        await browser.waitUntil(
            async () => {
                const el = await $('#oldPassword')
                return !(await el.isDisplayed())
            },
            {
                timeout: 60_000,
                timeoutMsg: '#oldPassword still visible after change',
            },
        )

        await setInputValue('#password', TEST_NEW_PASSWORD, 10_000)
        await submitLoginForm(5_000)

        await browser.waitUntil(
            async () => {
                const url = await browser.getUrl()
                return !url.includes('/login')
            },
            {
                timeout: 45_000,
                timeoutMsg:
                    'URL still contains /login after login with new password',
            },
        )

        const summaryAfterChange = await $(HEADING_XPATH('Summary'))
        await summaryAfterChange.waitForDisplayed({ timeout: 10_000 })

        const moreBtnRestore = await $('button[aria-label="More"]')
        await moreBtnRestore.waitForDisplayed({ timeout: 5_000 })
        await moreBtnRestore.click()

        const settingsBtnRestore = await $('button=Settings')
        await settingsBtnRestore.waitForDisplayed({ timeout: 5_000 })
        await settingsBtnRestore.click()

        const changePasswordBtnRestore = await $('button=Change encryption key')
        await changePasswordBtnRestore.waitForDisplayed({ timeout: 10_000 })
        await changePasswordBtnRestore.click()

        await setInputValue('#oldPassword', TEST_NEW_PASSWORD, 10_000)
        await setInputValue('#password', TEST_PASSWORD, 5_000)
        await setInputValue('#repeatPassword', TEST_PASSWORD, 5_000)
        await submitLoginForm(5_000)

        await browser.waitUntil(
            async () => {
                const el = await $('#oldPassword')
                return !(await el.isDisplayed())
            },
            {
                timeout: 60_000,
                timeoutMsg: '#oldPassword still visible after restore',
            },
        )

        await setInputValue('#password', TEST_PASSWORD, 10_000)
        await submitLoginForm(5_000)

        await browser.waitUntil(
            async () => {
                const url = await browser.getUrl()
                return !url.includes('/login')
            },
            {
                timeout: 45_000,
                timeoutMsg:
                    'URL still contains /login after login with restored password',
            },
        )

        const summaryRestored = await $(HEADING_XPATH('Summary'))
        await summaryRestored.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Investments page', async () => {
        await assertLoggedInForNav()
        const tab = await $('button[aria-label="Investments"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('My Assets'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Transactions page', async () => {
        await assertLoggedInForNav()
        const tab = await $('button[aria-label="Transactions"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Transactions'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Calculations page', async () => {
        await assertLoggedInForNav()
        const tab = await $('button[aria-label="Calculations"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Calculations'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to My Money page', async () => {
        await assertLoggedInForNav()
        const tab = await $('button[aria-label="My Money"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('My Money'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Integrations page', async () => {
        await assertLoggedInForNav()
        const tab = await $('button[aria-label="Integrations"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Integrations'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Export page via More menu', async () => {
        await assertLoggedInForNav()
        const moreBtn = await $('button[aria-label="More"]')
        await moreBtn.click()

        const exportBtn = await $('button=Export & Import')
        await exportBtn.waitForDisplayed({ timeout: 5_000 })
        await exportBtn.click()

        const heading = await $(HEADING_XPATH('Export & Import'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates back to Dashboard', async () => {
        await assertLoggedInForNav()
        const tab = await $('button[aria-label="Summary"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Summary'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })
})
