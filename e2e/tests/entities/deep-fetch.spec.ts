import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'

/**
 * Helper: connect Urbanitae and reload the page to populate entity accounts.
 */
async function connectUrbanitaeIfNeeded(page: import('@playwright/test').Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

    // Dismiss any overlay
    const cancelBtn = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await cancelBtn.click()
        await page.waitForTimeout(500)
    }

    const urbanitaeCard = page
        .locator('h3', { hasText: 'Urbanitae' })
        .first()
        .locator('../..')
    const fetchBtn = urbanitaeCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchBtn
        .isVisible({ timeout: 2_000 })
        .catch(() => false)

    if (!isConnected) {
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

        await page.reload()
        await page.waitForLoadState('networkidle')

        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }
}

test.describe('Deep Fetch / Force Refetch', () => {
    test('deep fetch retrieves additional older transactions', async ({
        authenticatedPage: page,
    }) => {
        await connectUrbanitaeIfNeeded(page)

        // First, do a normal fetch (all features, no deep mode)
        const urbanitaeCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        await urbanitaeCard.getByRole('button', { name: 'Fetch' }).click()
        await expect(
            page.getByText('Select features to fetch from Urbanitae'),
        ).toBeVisible({ timeout: 5_000 })

        // Wait for features to be auto-selected
        await expect(
            page.getByRole('button', { name: 'Fetch data' }),
        ).toBeEnabled({ timeout: 5_000 })

        await page.getByRole('button', { name: 'Fetch data' }).click()
        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })

        // Close the FeatureSelector overlay
        const cancelBtn1 = page.getByRole('button', { name: 'Cancel' })
        if (await cancelBtn1.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await cancelBtn1.click()
            await page.waitForTimeout(500)
        }

        // Verify normal transactions appear
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await expect(page.getByText('Mock Stock A').first()).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.getByText('Mock Stock B').first()).toBeVisible({
            timeout: 5_000,
        })
        // Old transaction should NOT be present yet
        await expect(page.getByText('Mock Stock Old')).not.toBeVisible()

        // Navigate back to Integrations for deep fetch
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Open FeatureSelector and enable deep fetch
        const urbanitaeCard2 = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        await urbanitaeCard2.getByRole('button', { name: 'Fetch' }).click()
        await expect(
            page.getByText('Select features to fetch from Urbanitae'),
        ).toBeVisible({ timeout: 5_000 })

        // Wait for features to be auto-selected
        await expect(
            page.getByRole('button', { name: 'Fetch data' }),
        ).toBeEnabled({ timeout: 5_000 })

        // Click "Advanced options" to show deep scrape toggle
        await page.getByText('Advanced options').click()

        // Enable the deep scrape switch
        await page.locator('button[role="switch"]').click()

        // Close the popover by clicking "Advanced options" again
        await page.getByText('Advanced options').click()
        await page.waitForTimeout(300)

        // Fetch data with deep mode
        await page.getByRole('button', { name: 'Fetch data' }).click()
        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })

        // Close the FeatureSelector overlay
        const cancelBtn2 = page.getByRole('button', { name: 'Cancel' })
        if (await cancelBtn2.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await cancelBtn2.click()
            await page.waitForTimeout(500)
        }

        // Verify old transaction now appears
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await expect(page.getByText('Mock Stock A').first()).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.getByText('Mock Stock B').first()).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.getByText('Mock Stock Old').first()).toBeVisible({
            timeout: 5_000,
        })
    })
})
