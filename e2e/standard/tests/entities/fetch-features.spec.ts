import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { selectEntity } from '../../helpers/entity-selector'
import { navigateToMyMoneyPage } from '../../helpers/my-money'

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

async function navigateToAutoContributions(page: Page) {
    await navigateToMyMoneyPage(page, 'Recurring')
    await page.getByRole('tab', { name: /^Investments/ }).click()
}

// MyInvestor: has POSITION, AUTO_CONTRIBUTIONS, TRANSACTIONS

test.describe('Feature Selection Verification', () => {
    test('EntityRefreshDropdown fetches ALL features', async ({
        authenticatedPage: page,
    }) => {
        // Use MyInvestor (has AUTO_CONTRIBUTIONS + TRANSACTIONS)
        await connectEntityIfNeeded(page, 'MyInvestor', {
            user: 'test@example.com',
            password: 'MockPassword123',
        })

        // Navigate to Summary/Dashboard
        await page.getByRole('button', { name: 'Summary' }).click()
        await page
            .getByRole('heading', { name: 'Summary' })
            .waitFor({ timeout: 10_000 })

        // Open Update dropdown and refresh MyInvestor (sends ALL features)
        await page.getByRole('button', { name: 'Update' }).click()
        await page
            .locator('button[aria-label="Refresh MyInvestor"]')
            .waitFor({ timeout: 5_000 })
        await page.locator('button[aria-label="Refresh MyInvestor"]').click()

        await expect(
            page.getByText('Data successfully fetched from MyInvestor'),
        ).toBeVisible({ timeout: 30_000 })

        // Dismiss the Data dropdown overlay via JS (it blocks all pointer events)
        await page.evaluate(() => {
            document.querySelectorAll('div.fixed').forEach((el) => {
                if (
                    el instanceof HTMLElement &&
                    el.classList.contains('inset-0') &&
                    el.classList.contains('z-40')
                ) {
                    el.click()
                }
            })
        })
        await page.waitForTimeout(500)

        // Verify TRANSACTIONS feature was included (transactions appear)
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await page
            .getByRole('radio', { name: 'Investments', exact: true })
            .click()
        await selectEntity(page, 'MyInvestor')
        await page.keyboard.press('Escape')
        await page.getByRole('button', { name: 'Search', exact: true }).click()
        await expect(page.getByText('Mock Stock A').first()).toBeVisible({
            timeout: 5_000,
        })

        // Verify AUTO_CONTRIBUTIONS feature was included
        await navigateToAutoContributions(page)
        await expect(page.getByText('Mock ETF Plan').first()).toBeVisible({
            timeout: 5_000,
        })
    })

    test('FeatureSelector fetches only selected features', async ({
        authenticatedPage: page,
    }) => {
        // Start with clean state: disconnect MyInvestor if connected
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Dismiss any overlay
        const cancelOverlay = page.getByRole('button', { name: 'Cancel' })
        if (
            await cancelOverlay.isVisible({ timeout: 1_000 }).catch(() => false)
        ) {
            await cancelOverlay.click()
            await page.waitForTimeout(500)
        }

        const myInvestorCard = page
            .locator('h3', { hasText: 'MyInvestor' })
            .first()
            .locator('../..')
        const disconnectBtn = myInvestorCard.locator(
            'button.text-red-600, button.text-red-500',
        )
        if (
            await disconnectBtn.isVisible({ timeout: 2_000 }).catch(() => false)
        ) {
            await disconnectBtn.click()
            await expect(page.getByText('Confirm Disconnect')).toBeVisible({
                timeout: 5_000,
            })
            await page.getByRole('button', { name: 'Disconnect' }).click()
            await expect(
                page.getByText('Entity disconnected successfully'),
            ).toBeVisible({ timeout: 10_000 })
            await page.reload()
            await page.waitForLoadState('networkidle')
        }

        // Disconnect ALL other entities that may have leftover transactions
        for (const otherEntity of [
            'Urbanitae',
            'Trade Republic',
            'DEGIRO',
            'Wecity',
        ]) {
            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 15_000 })
            const otherCard = page
                .locator('h3', { hasText: otherEntity })
                .first()
                .locator('../..')
            const otherDisconnect = otherCard.locator(
                'button.text-red-600, button.text-red-500',
            )
            if (
                await otherDisconnect
                    .isVisible({ timeout: 1_000 })
                    .catch(() => false)
            ) {
                await otherDisconnect.click()
                await expect(page.getByText('Confirm Disconnect')).toBeVisible({
                    timeout: 5_000,
                })
                await page.getByRole('button', { name: 'Disconnect' }).click()
                await expect(
                    page.getByText('Entity disconnected successfully'),
                ).toBeVisible({ timeout: 10_000 })
                await page.reload()
                await page.waitForLoadState('networkidle')
            }
        }

        // Now connect MyInvestor fresh
        await connectEntityIfNeeded(page, 'MyInvestor', {
            user: 'test@example.com',
            password: 'MockPassword123',
        })

        // Open FeatureSelector for MyInvestor
        const entityCard = page
            .locator('h3', { hasText: 'MyInvestor' })
            .first()
            .locator('../..')
        await entityCard.getByRole('button', { name: 'Fetch' }).click()

        await expect(
            page.getByText('Select features to fetch from MyInvestor'),
        ).toBeVisible({ timeout: 5_000 })

        // Wait for features to be auto-selected
        const modalFetch = page
            .locator('.fixed')
            .getByRole('button', { name: 'Fetch' })
        await expect(modalFetch).toBeEnabled({
            timeout: 5_000,
        })

        // Deselect Transactions — click the h-24 feature toggle button
        await page.locator('button.h-24', { hasText: 'Transactions' }).click()

        // Fetch with only POSITION and AUTO_CONTRIBUTIONS
        await modalFetch.click()
        await expect(
            page.getByText('Data successfully fetched from MyInvestor'),
        ).toBeVisible({ timeout: 30_000 })

        await expect(
            page.getByText('Select features to fetch from MyInvestor'),
        ).toBeHidden()

        // Transactions page should NOT show MyInvestor mock transactions (TRANSACTIONS was excluded)
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await page
            .getByRole('radio', { name: 'Investments', exact: true })
            .click()
        const entityFilter = page.getByRole('combobox').first()
        if (await entityFilter.isEnabled()) {
            await entityFilter.click()
            const popover = page
                .locator('[data-radix-popper-content-wrapper]')
                .last()
            await expect(popover).toBeVisible()
            await expect(
                popover.getByRole('button', {
                    name: 'MyInvestor',
                    exact: true,
                }),
            ).toHaveCount(0)
            await page.keyboard.press('Escape')
        } else {
            await expect(entityFilter).toBeDisabled()
        }
        await page.getByRole('button', { name: 'Search', exact: true }).click()
        await expect(page.getByText('Mock Stock A').first()).not.toBeVisible({
            timeout: 5_000,
        })

        // But Auto Contributions SHOULD be present
        await navigateToAutoContributions(page)
        await expect(page.getByText('Mock ETF Plan').first()).toBeVisible({
            timeout: 10_000,
        })
    })
})
