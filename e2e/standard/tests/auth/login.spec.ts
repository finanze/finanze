import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { TEST_PASSWORD } from '../../helpers/constants'

test.describe('Login Existing User', () => {
    test('login after logout shows dashboard', async ({
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

        // Login with correct password
        await page.fill('#password', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        // Should return to dashboard
        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })
    })
})
