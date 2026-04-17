import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'

test.describe('Disconnect Entity (Urbanitae)', () => {
    test('disconnect entity removes it from connected list', async ({
        authenticatedPage: page,
    }) => {
        // Navigate to entities
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Check if Urbanitae is already connected (from a prior test run)
        const connectedHeading = page.getByText('Connected').first()
        const isAlreadyConnected = await connectedHeading
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!isAlreadyConnected) {
            // Connect Urbanitae first
            await page.getByText('Urbanitae').first().click()
            await page
                .getByText('Enter credentials for')
                .waitFor({ timeout: 5_000 })
            await page.locator('#user').fill('test@example.com')
            await page.locator('#password').fill('MockPassword123')
            await page.getByRole('button', { name: 'Submit' }).click()
            await expect(
                page.getByText('Successfully logged in to Urbanitae'),
            ).toBeVisible({ timeout: 15_000 })

            // Reload to ensure entity accounts are populated from the backend
            await page.reload()
            await page.waitForLoadState('networkidle')

            // Navigate to Integrations
            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 15_000 })
        }

        // Verify entity is in Connected section
        await expect(page.getByText('Connected').first()).toBeVisible({
            timeout: 5_000,
        })

        // Click the disconnect button (red Unplug icon) on Urbanitae card
        const urbanitaeCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        const disconnectButton = urbanitaeCard.locator(
            'button.text-red-600, button.text-red-500',
        )
        await disconnectButton.click()

        // Confirmation dialog should appear
        await expect(page.getByText('Confirm Disconnect')).toBeVisible({
            timeout: 5_000,
        })

        // Click "Disconnect" to confirm
        await page.getByRole('button', { name: 'Disconnect' }).click()

        // Success toast should appear
        await expect(
            page.getByText('Entity disconnected successfully'),
        ).toBeVisible({ timeout: 10_000 })

        // Urbanitae should now be in "Available Entities" (disconnected state)
        await expect(page.getByText('Available Entities')).toBeVisible({
            timeout: 5_000,
        })
    })
})
