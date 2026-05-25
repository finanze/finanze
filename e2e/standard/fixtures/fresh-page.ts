import { test as backendTest } from './backend'
import { BACKEND_PORT } from '../helpers/constants'

export const test = backendTest.extend<{
    freshPage: import('@playwright/test').Page
}>({
    freshPage: async ({ page, backend }, use) => {
        const freshPort = new URL(backend.backendUrl).port

        if (String(BACKEND_PORT) !== freshPort) {
            await page.route('**/api/v1/**', async (route) => {
                const url = route
                    .request()
                    .url()
                    .replace(`:${BACKEND_PORT}/`, `:${freshPort}/`)
                await route.continue({ url })
            })
        }

        await page.goto('/')
        await page.locator('#username').waitFor({ timeout: 20_000 })

        await use(page)
    },
})
