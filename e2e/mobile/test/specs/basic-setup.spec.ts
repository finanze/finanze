import { switchToWebView } from '../helpers/webview.js'
import {
    TEST_USER,
    TEST_PASSWORD,
    TEST_NEW_PASSWORD,
} from '../helpers/constants.js'

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

    it('change password and re-login works', async () => {
        const moreBtn = await $('button[aria-label="More"]')
        await moreBtn.waitForDisplayed({ timeout: 5_000 })
        await moreBtn.click()

        const settingsBtn = await $('button=Settings')
        await settingsBtn.waitForDisplayed({ timeout: 5_000 })
        await settingsBtn.click()

        const changePasswordBtn = await $('button=Change Password')
        await changePasswordBtn.waitForDisplayed({ timeout: 10_000 })
        await changePasswordBtn.click()

        const oldPasswordField = await $('#oldPassword')
        await oldPasswordField.waitForDisplayed({ timeout: 10_000 })
        await oldPasswordField.setValue(TEST_PASSWORD)
        const newPasswordField = await $('#password')
        await newPasswordField.setValue(TEST_NEW_PASSWORD)
        const repeatField = await $('#repeatPassword')
        await repeatField.setValue(TEST_NEW_PASSWORD)
        const submitChangeBtn = await $('button[type="submit"]')
        await submitChangeBtn.waitForClickable({ timeout: 5_000 })
        await submitChangeBtn.click()

        await browser.waitUntil(
            async () => {
                const el = await $('#oldPassword')
                return !(await el.isDisplayed())
            },
            {
                timeout: 10_000,
                timeoutMsg: '#oldPassword still visible after change',
            },
        )

        const loginPassword = await $('#password')
        await loginPassword.waitForDisplayed({ timeout: 10_000 })
        await loginPassword.setValue(TEST_NEW_PASSWORD)
        const loginBtn = await $('button[type="submit"]')
        await loginBtn.waitForClickable({ timeout: 5_000 })
        await loginBtn.click()

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

        const changePasswordBtnRestore = await $('button=Change Password')
        await changePasswordBtnRestore.waitForDisplayed({ timeout: 10_000 })
        await changePasswordBtnRestore.click()

        const oldPasswordRestore = await $('#oldPassword')
        await oldPasswordRestore.waitForDisplayed({ timeout: 10_000 })
        await oldPasswordRestore.setValue(TEST_NEW_PASSWORD)
        const newPasswordRestore = await $('#password')
        await newPasswordRestore.setValue(TEST_PASSWORD)
        const repeatRestore = await $('#repeatPassword')
        await repeatRestore.setValue(TEST_PASSWORD)
        const submitRestoreBtn = await $('button[type="submit"]')
        await submitRestoreBtn.waitForClickable({ timeout: 5_000 })
        await submitRestoreBtn.click()

        await browser.waitUntil(
            async () => {
                const el = await $('#oldPassword')
                return !(await el.isDisplayed())
            },
            {
                timeout: 10_000,
                timeoutMsg: '#oldPassword still visible after restore',
            },
        )

        const restorePassword = await $('#password')
        await restorePassword.waitForDisplayed({ timeout: 10_000 })
        await restorePassword.setValue(TEST_PASSWORD)
        const restoreLoginBtn = await $('button[type="submit"]')
        await restoreLoginBtn.waitForClickable({ timeout: 5_000 })
        await restoreLoginBtn.click()

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
