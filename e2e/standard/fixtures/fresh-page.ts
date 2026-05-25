import { test as backendTest } from './backend'

export const test = backendTest.extend<{
    freshPage: import('@playwright/test').Page
}>({
    freshPage: async ({ page, backend }, use) => {
        await page.goto('/')
        await page.locator('#username').waitFor({ timeout: 20_000 })

        await use(page)
    },
})
