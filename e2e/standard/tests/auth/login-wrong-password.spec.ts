import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'

test.describe('Login Wrong Password', () => {
    test('wrong password shows error message', async ({
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

        // Try wrong password
        await page.fill('#password', 'WrongPassword!')
        await page.locator('button[type="submit"]').click()

        // Error message should appear
        await expect(page.getByText('Invalid credentials')).toBeVisible({
            timeout: 5_000,
        })

        // Should still be on login page
        await expect(page.locator('#password')).toBeVisible()
    })
})
