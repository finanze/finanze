import { switchToWebView } from '../helpers/webview.js'
import { TEST_USER, TEST_PASSWORD } from '../helpers/constants.js'

const HEADING_XPATH = (text: string) =>
    `//*[self::h1 or self::h2 or self::h3 or self::h4][contains(text(),"${text}")]`

describe('Basic Setup', () => {
    before(async () => {
        await switchToWebView()
        await driver.pause(500)

        const username = await $('#username')
        await username.waitForDisplayed({ timeout: 30_000 })

        await $('#username').setValue(TEST_USER)
        const password = await $('#password')
        await password.waitForDisplayed({ timeout: 5_000 })
        await password.setValue(TEST_PASSWORD)
        const repeatPassword = await $('#repeatPassword')
        await repeatPassword.waitForDisplayed({ timeout: 5_000 })
        await repeatPassword.setValue(TEST_PASSWORD)
        const submitBtn = await $('button[type="submit"]')
        await submitBtn.waitForClickable({ timeout: 5_000 })
        await submitBtn.click()

        await browser.waitUntil(
            async () => {
                const url = await browser.getUrl()
                return !url.includes('/login')
            },
            {
                timeout: 45_000,
                timeoutMsg: 'URL still contains /login after signup',
            },
        )

        const summary = await $(HEADING_XPATH('Summary'))
        await summary.waitForDisplayed({ timeout: 10_000 })

        const moreBtn = await $('button[aria-label="More"]')
        await moreBtn.waitForDisplayed({ timeout: 5_000 })
        await moreBtn.click()

        const settingsBtn = await $('button=Settings')
        await settingsBtn.waitForDisplayed({ timeout: 5_000 })
        await settingsBtn.click()

        const logoutBtn = await $('button.text-red-500=Logout')
        await logoutBtn.waitForDisplayed({ timeout: 5_000 })
        await logoutBtn.click()

        const passwordField = await $('#password')
        await passwordField.waitForDisplayed({ timeout: 10_000 })
    })

    it('login after logout shows dashboard', async () => {
        await expect($('#username')).not.toBeDisplayed()

        const password = await $('#password')
        await password.waitForDisplayed({ timeout: 5_000 })
        await password.setValue(TEST_PASSWORD)
        const submitBtn = await $('button[type="submit"]')
        await submitBtn.waitForClickable({ timeout: 5_000 })
        await submitBtn.click()

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

    it('navigates to Investments page', async () => {
        const tab = await $('button[aria-label="Investments"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('My Assets'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Transactions page', async () => {
        const tab = await $('button[aria-label="Transactions"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Transactions'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Calculations page', async () => {
        const tab = await $('button[aria-label="Calculations"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Calculations'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Management page', async () => {
        const tab = await $('button[aria-label="Management"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Management'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Integrations page', async () => {
        const tab = await $('button[aria-label="Integrations"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Integrations'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates to Export page via More menu', async () => {
        const moreBtn = await $('button[aria-label="More"]')
        await moreBtn.click()

        const exportBtn = await $('button=Export & Import')
        await exportBtn.waitForDisplayed({ timeout: 5_000 })
        await exportBtn.click()

        const heading = await $(HEADING_XPATH('Export & Import'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })

    it('navigates back to Dashboard', async () => {
        const tab = await $('button[aria-label="Summary"]')
        await tab.click()

        const heading = await $(HEADING_XPATH('Summary'))
        await heading.waitForDisplayed({ timeout: 10_000 })
    })
})
