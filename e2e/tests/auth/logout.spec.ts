import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'

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
        const status = await page.evaluate(async () => {
            const res = await fetch('http://localhost:7592/api/v1/status')
            return res.json()
        })
        expect(status.status).toBe('LOCKED')
    })
})
