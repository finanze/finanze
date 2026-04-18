import { expect } from '@playwright/test'
import { test as backendTest } from './backend'
import { TEST_USER, TEST_PASSWORD } from '../helpers/constants'

export const test = backendTest.extend<{
    authenticatedPage: import('@playwright/test').Page
}>({
    authenticatedPage: async ({ page, backend }, use) => {
        // Ensure backend is locked before starting
        await fetch(`${backend.backendUrl}/api/v1/logout`, {
            method: 'POST',
        }).catch(() => {})

        // Check if a user already exists
        const statusRes = await fetch(`${backend.backendUrl}/api/v1/status`)
        const status = await statusRes.json()

        await page.goto('/')

        if (status.lastLogged) {
            // User exists — login
            await page.locator('#password').waitFor({ timeout: 20_000 })
            await page.fill('#password', TEST_PASSWORD)
        } else {
            // No user — signup
            await page.locator('#username').waitFor({ timeout: 20_000 })
            await page.fill('#username', TEST_USER)
            await page.fill('#password', TEST_PASSWORD)
            await page.fill('#repeatPassword', TEST_PASSWORD)
        }

        await page.locator('button[type="submit"]').click()

        // Wait for dashboard to fully load
        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        await use(page)
    },
})
