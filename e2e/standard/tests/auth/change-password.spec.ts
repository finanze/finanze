import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { TEST_PASSWORD, TEST_NEW_PASSWORD } from '../../helpers/constants'

test.describe('Change Encryption Key', () => {
    test('change encryption key flow works end-to-end', async ({
        authenticatedPage: page,
    }) => {
        // Use sidebar popover to click Change Encryption Key
        await page.locator('button[aria-label="Logout"]').click()
        await page
            .getByRole('button', { name: 'Change encryption key' })
            .waitFor()
        await page
            .getByRole('button', { name: 'Change encryption key' })
            .click()

        // Login page should appear in change-password mode
        await page.locator('#oldPassword').waitFor({ timeout: 10_000 })

        // Fill change password form
        await page.fill('#oldPassword', TEST_PASSWORD)
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.fill('#repeatPassword', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        // After success, login page appears for normal login
        await expect(page.locator('#oldPassword')).not.toBeVisible({
            timeout: 10_000,
        })
        await page.locator('#password').waitFor({ timeout: 10_000 })

        // Login with new password
        await page.fill('#password', TEST_NEW_PASSWORD)
        await page.locator('button[type="submit"]').click()

        // Should be back on dashboard
        await expect(page).not.toHaveURL(/login/, { timeout: 20_000 })
        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        // Restore original encryption key so other tests are not affected
        await page.locator('button[aria-label="Logout"]').click()
        await page
            .getByRole('button', { name: 'Change encryption key' })
            .waitFor()
        await page
            .getByRole('button', { name: 'Change encryption key' })
            .click()

        await page.locator('#oldPassword').waitFor({ timeout: 10_000 })
        await page.fill('#oldPassword', TEST_NEW_PASSWORD)
        await page.fill('#password', TEST_PASSWORD)
        await page.fill('#repeatPassword', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(page.locator('#oldPassword')).not.toBeVisible({
            timeout: 10_000,
        })
    })
})
