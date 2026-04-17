import { switchToWebView } from '../helpers/webview.js'
import { TEST_USER, TEST_PASSWORD } from '../helpers/constants.js'

describe('Signup', () => {
    it('signup with valid credentials transitions to dashboard', async () => {
        await switchToWebView()

        const username = await $('#username')
        await username.waitForDisplayed({ timeout: 20_000 })

        await $('#username').setValue(TEST_USER)
        await $('#password').setValue(TEST_PASSWORD)
        await $('#repeatPassword').setValue(TEST_PASSWORD)
        await $('button[type="submit"]').click()

        await browser.waitUntil(
            async () => {
                const url = await browser.getUrl()
                return !url.includes('/login')
            },
            {
                timeout: 20_000,
                timeoutMsg: 'URL still contains /login after signup',
            },
        )

        const summary = await $(
            '//*[self::h1 or self::h2 or self::h3 or self::h4][text()="Summary"]',
        )
        await summary.waitForDisplayed({ timeout: 10_000 })
    })
})
