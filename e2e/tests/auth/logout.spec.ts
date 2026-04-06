import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { BACKEND_URL } from '../../helpers/constants'

test.describe('Logout', () => {
    test('logout returns to login screen', async ({
        authenticatedPage: page,
    }) => {
        // Logout via sidebar popover
        await page.locator('button[aria-label="Logout"]').click()
        await page
            .locator('button.text-red-500', { hasText: 'Logout' })
            .waitFor()
        await page.locator('button.text-red-500', { hasText: 'Logout' }).click()

        // Wait for login page
        await page.locator('#password').waitFor({ timeout: 10_000 })
        await expect(page.locator('#password')).toBeVisible()

        // Verify status is LOCKED via API
        const apiUrl = `${BACKEND_URL}/api/v1/status`
        const status = await page.evaluate(async (url) => {
            const res = await fetch(url)
            return res.json()
        }, apiUrl)
        expect(status.status).toBe('LOCKED')
    })
})
