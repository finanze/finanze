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

    test('enable error reporting from login hides the action', async ({
        authenticatedPage: page,
    }) => {
        await page.locator('button[aria-label="Settings"]').first().click()
        const errorReporting = page.getByTestId('telemetry-error-reporting')
        await errorReporting.waitFor({ timeout: 10_000 })
        if ((await errorReporting.getAttribute('data-state')) === 'checked') {
            await errorReporting.click()
            await expect(errorReporting).toHaveAttribute(
                'data-state',
                'unchecked',
            )
        }

        await page.getByRole('button', { name: 'Summary' }).click()
        await page
            .getByRole('heading', { name: 'Summary' })
            .waitFor({ timeout: 10_000 })

        await page.locator('button[aria-label="Logout"]').click()
        await page
            .locator('button.text-red-500', { hasText: 'Logout' })
            .waitFor()
        await page.locator('button.text-red-500', { hasText: 'Logout' }).click()
        await page.locator('#password').waitFor({ timeout: 10_000 })

        const enableButton = page.getByTestId('login-enable-error-reporting')
        await expect(enableButton).toBeVisible()

        await enableButton.click()
        await page.getByTestId('telemetry-consent-enable').click()

        await expect(enableButton).toHaveCount(0)
    })
})
