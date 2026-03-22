import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

/**
 * Helper: connect an entity via login form and reload.
 */
async function connectEntityIfNeeded(
    page: Page,
    entityName: string,
    credentials: Record<string, string>,
) {
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

    const entityCard = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchBtn = entityCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchBtn
        .isVisible({ timeout: 3_000 })
        .catch(() => false)

    if (!isConnected) {
        await page.getByText(entityName).first().click()
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 10_000 })
        for (const [field, value] of Object.entries(credentials)) {
            await page.locator(`#${field}`).fill(value)
        }
        await page.getByRole('button', { name: 'Submit' }).click()
        await expect(
            page.getByText(`Successfully logged in to ${entityName}`),
        ).toBeVisible({ timeout: 30_000 })

        await page.reload()
        await page.waitForLoadState('networkidle')

        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }
}

/**
 * Helper: fetch all features for an entity from Integrations page.
 * Waits for features to be selected, clicks Fetch data, waits for success, then closes overlay.
 */
async function fetchEntityAllFeatures(page: Page, entityName: string) {
    const entityCard = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    await entityCard.getByRole('button', { name: 'Fetch' }).click()

    await expect(
        page.getByText(`Select features to fetch from ${entityName}`),
    ).toBeVisible({ timeout: 5_000 })

    // Wait for features to be auto-selected (Fetch data button becomes enabled)
    await expect(page.getByRole('button', { name: 'Fetch data' })).toBeEnabled({
        timeout: 5_000,
    })

    await page.getByRole('button', { name: 'Fetch data' }).click()

    await expect(
        page.getByText(`Data successfully fetched from ${entityName}`),
    ).toBeVisible({ timeout: 30_000 })

    // Close the FeatureSelector overlay by clicking Cancel
    const cancelBtn = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await cancelBtn.click()
        await page.waitForTimeout(500)
    }
}

/**
 * Helper: navigate to Auto Contributions page via sidebar Management section.
 */
async function navigateToAutoContributions(page: Page) {
    // Click Management to expand the section
    const mgmtBtn = page
        .getByRole('navigation')
        .getByRole('button', { name: 'Management' })
    await mgmtBtn.click()
    await page.waitForTimeout(500)
    // Click Auto Contributions sub-item (scoped to nav to avoid matching page buttons)
    await page
        .getByRole('navigation')
        .getByRole('button', { name: 'Auto Contributions' })
        .click()
    // Wait for page to load
    await page.waitForTimeout(1_000)
}

// Urbanitae: has POSITION, TRANSACTIONS, HISTORIC (no AUTO_CONTRIBUTIONS)
// MyInvestor: has POSITION, AUTO_CONTRIBUTIONS, TRANSACTIONS

test.describe('Fetch Entity Data - Transactions', () => {
    test('fetched transactions appear in TransactionsPage', async ({
        authenticatedPage: page,
    }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', {
            user: 'test@example.com',
            password: 'MockPassword123',
        })
        await fetchEntityAllFeatures(page, 'Urbanitae')

        // Navigate to Transactions page
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })

        // Verify mock transactions are visible
        await expect(page.getByText('Mock Stock A').first()).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.getByText('Mock Stock B').first()).toBeVisible({
            timeout: 5_000,
        })
    })
})

test.describe('Fetch Entity Data - Auto Contributions', () => {
    test('fetched auto-contributions appear in AutoContributionsPage', async ({
        authenticatedPage: page,
    }) => {
        // MyInvestor has AUTO_CONTRIBUTIONS feature
        await connectEntityIfNeeded(page, 'MyInvestor', {
            user: 'test@example.com',
            password: 'MockPassword123',
        })
        await fetchEntityAllFeatures(page, 'MyInvestor')

        await navigateToAutoContributions(page)

        // Verify mock contribution is visible
        await expect(page.getByText('Mock ETF Plan').first()).toBeVisible({
            timeout: 5_000,
        })
    })
})

test.describe('Fetch Entity Data - Disconnect Cleanup', () => {
    test('disconnect removes transactions and contributions', async ({
        authenticatedPage: page,
    }) => {
        // Connect and fetch MyInvestor (has both TRANSACTIONS and AUTO_CONTRIBUTIONS)
        await connectEntityIfNeeded(page, 'MyInvestor', {
            user: 'test@example.com',
            password: 'MockPassword123',
        })
        await fetchEntityAllFeatures(page, 'MyInvestor')

        // Verify data exists before disconnect
        await navigateToAutoContributions(page)
        await expect(page.getByText('Mock ETF Plan').first()).toBeVisible({
            timeout: 5_000,
        })

        // Disconnect MyInvestor
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const entityCard = page
            .locator('h3', { hasText: 'MyInvestor' })
            .first()
            .locator('../..')
        const disconnectButton = entityCard.locator(
            'button.text-red-600, button.text-red-500',
        )
        await disconnectButton.click()

        await expect(page.getByText('Confirm Disconnect')).toBeVisible({
            timeout: 5_000,
        })
        await page.getByRole('button', { name: 'Disconnect' }).click()
        await expect(
            page.getByText('Entity disconnected successfully'),
        ).toBeVisible({ timeout: 10_000 })

        // Also disconnect Urbanitae if it's connected (from prior test in same worker)
        await page.reload()
        await page.waitForLoadState('networkidle')
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const urbanitaeCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        const urbanitaeDisconnect = urbanitaeCard.locator(
            'button.text-red-600, button.text-red-500',
        )
        if (
            await urbanitaeDisconnect
                .isVisible({ timeout: 2_000 })
                .catch(() => false)
        ) {
            await urbanitaeDisconnect.click()
            await expect(page.getByText('Confirm Disconnect')).toBeVisible({
                timeout: 5_000,
            })
            await page.getByRole('button', { name: 'Disconnect' }).click()
            await expect(
                page.getByText('Entity disconnected successfully'),
            ).toBeVisible({ timeout: 10_000 })
        }

        // Verify MyInvestor and Urbanitae transactions are gone
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await expect(page.getByText('Mock Stock A').first()).not.toBeVisible()
        await expect(page.getByText('Mock Stock B').first()).not.toBeVisible()

        // Verify contributions are gone
        await navigateToAutoContributions(page)
        await expect(page.getByText('No auto contributions')).toBeVisible({
            timeout: 5_000,
        })
    })
})
