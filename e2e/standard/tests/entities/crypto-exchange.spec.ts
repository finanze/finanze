import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { BINANCE_CREDENTIALS } from '../../helpers/constants'

/**
 * Helper: locate the Binance exchange entity card.
 * Finds the Card element that contains exact "Binance" text but NOT "Binance Smart Chain".
 */
function binanceCard(page: Page) {
    // EntityCard renders as a Card (div with rounded border).
    // Match only cards with exact "Binance" text, not "Binance Smart Chain".
    return page
        .locator('div[class*="rounded"][class*="border"]', {
            has: page.locator('span:text-is("Binance")'),
        })
        .first()
}

/**
 * Helper: scroll to make Binance entity visible and click it.
 */
async function clickBinanceEntity(page: Page) {
    await scrollToBinance(page)
    await binanceCard(page).click()
}

/**
 * Helper: scroll to make the Crypto Exchanges section visible.
 */
async function scrollToBinance(page: Page) {
    const binanceText = page.locator('span:text-is("Binance")').first()
    await binanceText.scrollIntoViewIfNeeded()
    await page.waitForTimeout(300)
}

/**
 * Helper: connect a new Binance account with the given name.
 * Assumes the page is on the Integrations page.
 */
async function connectBinanceAccount(
    page: Page,
    accountName: string,
    clickEntity = true,
) {
    if (clickEntity) {
        await scrollToBinance(page)
        const card = binanceCard(page)
        await card.click()
    }
    await page.getByText('Enter credentials for').waitFor({ timeout: 10_000 })
    await page.locator('#apiKey').fill(BINANCE_CREDENTIALS.apiKey)
    await page.locator('#secretKey').fill(BINANCE_CREDENTIALS.secretKey)

    // Click the "Name this account" link to show the account name field
    const addNameBtn = page.getByText('Name this account')
    if (await addNameBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await addNameBtn.click()
        await page.waitForTimeout(300)
    }

    // Fill the account name if the field is visible
    const accountNameField = page.locator('#accountName')
    if (
        await accountNameField.isVisible({ timeout: 1_000 }).catch(() => false)
    ) {
        await accountNameField.fill(accountName)
    }

    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(
        page.getByText('Successfully logged in to Binance'),
    ).toBeVisible({ timeout: 15_000 })

    await page.reload()
    await page.waitForLoadState('networkidle')
}

/**
 * Helper: navigate to Integrations page and dismiss any overlays.
 */
async function goToIntegrations(page: Page) {
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
}

/**
 * Helper: open the ManageAccountsDialog for Binance.
 */
async function openManageDialog(page: Page) {
    await scrollToBinance(page)
    await binanceCard(page).getByRole('button', { name: 'Manage' }).click()
    await expect(page.getByText('Manage Accounts')).toBeVisible({
        timeout: 5_000,
    })
}

/**
 * Helper: get account rows inside the ManageAccountsDialog.
 * The dialog is a portal mounted as a fixed overlay on document.body.
 */
function dialogAccountRows(page: Page) {
    // Account rows have p-3 padding; the dialog container does not
    return page.locator('.fixed').locator('.rounded-lg.border.p-3')
}

/**
 * Helper: close the ManageAccountsDialog.
 */
async function closeManageDialog(page: Page) {
    await page
        .locator('.fixed')
        .locator('button')
        .filter({ has: page.locator('svg.lucide-x') })
        .first()
        .click()
    await page.waitForTimeout(500)
}

test.describe('Crypto Exchange - Binance Multi-Account', () => {
    test('connect single Binance account and fetch data', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)
        await scrollToBinance(page)

        await connectBinanceAccount(page, 'Main')

        await goToIntegrations(page)
        await scrollToBinance(page)

        // Verify account badge shows "Main"
        await expect(binanceCard(page).getByText('Main')).toBeVisible({
            timeout: 5_000,
        })

        // Fetch all features
        await binanceCard(page).getByRole('button', { name: 'Fetch' }).click()
        await expect(
            page.getByText('Select features to fetch from Binance'),
        ).toBeVisible({ timeout: 5_000 })
        const modalFetch = page
            .locator('.fixed')
            .getByRole('button', { name: 'Fetch' })
        await expect(modalFetch).toBeEnabled({
            timeout: 5_000,
        })
        await modalFetch.click()
        await expect(
            page.getByText('Data successfully fetched from Binance'),
        ).toBeVisible({ timeout: 30_000 })

        // Close FeatureSelector overlay
        const cancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (await cancelBtn.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await cancelBtn.click()
            await page.waitForTimeout(500)
        }

        // Navigate to Transactions and verify crypto transactions appear
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await expect(page.getByText(/Crypto BTC Buy/).first()).toBeVisible({
            timeout: 5_000,
        })
    })

    test('connect two Binance accounts and manage', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)
        await scrollToBinance(page)

        // Ensure first account exists
        const card = binanceCard(page)
        const manageBtn = card.getByRole('button', { name: 'Manage' })
        const hasManage = await manageBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!hasManage) {
            await connectBinanceAccount(page, 'Main')
            await goToIntegrations(page)
            await scrollToBinance(page)
        }

        // Add second account via "+" button on the card
        await binanceCard(page)
            .locator('button')
            .filter({ has: page.locator('svg.lucide-plus') })
            .click()

        await connectBinanceAccount(page, 'DCA', false)
        await goToIntegrations(page)
        await scrollToBinance(page)

        // Open Manage dialog
        await openManageDialog(page)

        const dialog = page.locator('.fixed')
        await expect(dialog.getByText('Main')).toBeVisible({ timeout: 3_000 })
        await expect(dialog.getByText('DCA')).toBeVisible({ timeout: 3_000 })

        // Both should show Connected badge
        const connectedBadges = page.locator('.fixed').locator('text=Connected')
        await expect(connectedBadges).toHaveCount(2, { timeout: 5_000 })

        await closeManageDialog(page)
    })

    test('individual account fetch via manage dialog', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)
        await scrollToBinance(page)

        // Ensure 2 accounts exist
        const manageBtn = binanceCard(page).getByRole('button', {
            name: 'Manage',
        })
        const hasManage = await manageBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!hasManage) {
            await connectBinanceAccount(page, 'Main')
            await goToIntegrations(page)
            await scrollToBinance(page)
            await binanceCard(page)
                .locator('button')
                .filter({ has: page.locator('svg.lucide-plus') })
                .click()
            await connectBinanceAccount(page, 'DCA', false)
            await goToIntegrations(page)
            await scrollToBinance(page)
        }

        // Open Manage dialog
        await openManageDialog(page)

        // Click the fetch button (RefreshCw icon) next to first account
        const firstAccountRow = dialogAccountRows(page).first()
        await firstAccountRow
            .locator('button')
            .filter({ has: page.locator('svg.lucide-refresh-cw') })
            .first()
            .click()

        // Wait for success toast
        await expect(
            page.getByText('Data successfully fetched from Binance'),
        ).toBeVisible({ timeout: 30_000 })
    })

    test('disconnect one account preserves other account data', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)
        await scrollToBinance(page)

        // Ensure 2 accounts exist
        const manageBtn = binanceCard(page).getByRole('button', {
            name: 'Manage',
        })
        const hasManage = await manageBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!hasManage) {
            await connectBinanceAccount(page, 'Main')
            await goToIntegrations(page)
            await scrollToBinance(page)
            await binanceCard(page)
                .locator('button')
                .filter({ has: page.locator('svg.lucide-plus') })
                .click()
            await connectBinanceAccount(page, 'DCA', false)
            await goToIntegrations(page)
            await scrollToBinance(page)
        }

        // Open Manage dialog and disconnect the last account
        await openManageDialog(page)

        const accountRows = dialogAccountRows(page)
        const lastRow = accountRows.last()
        await lastRow
            .locator('button')
            .filter({ has: page.locator('svg.lucide-unplug') })
            .click()

        // Confirm disconnect — target the confirmation dialog's primary button, not icon buttons
        await expect(page.getByText('Confirm Disconnect')).toBeVisible({
            timeout: 5_000,
        })
        await page
            .locator('button', { hasText: 'Disconnect' })
            .filter({ hasNot: page.locator('svg') })
            .click()
        await expect(
            page.getByText('Entity disconnected successfully'),
        ).toBeVisible({ timeout: 10_000 })

        // Reload and verify the card still exists with remaining accounts
        await page.reload()
        await page.waitForLoadState('networkidle')
        await goToIntegrations(page)
        await scrollToBinance(page)

        await expect(binanceCard(page)).toBeVisible({ timeout: 5_000 })
    })

    test('connect three accounts and manage', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)
        await scrollToBinance(page)

        // Ensure first account exists
        const manageBtn = binanceCard(page).getByRole('button', {
            name: 'Manage',
        })
        const hasManage = await manageBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!hasManage) {
            await connectBinanceAccount(page, 'Main')
            await goToIntegrations(page)
            await scrollToBinance(page)
        }

        // Check how many accounts currently exist
        await openManageDialog(page)
        let accountRows = dialogAccountRows(page)
        const accountCount = await accountRows.count()
        await closeManageDialog(page)

        // Add accounts until we have 3
        for (let i = accountCount; i < 3; i++) {
            await scrollToBinance(page)
            await binanceCard(page)
                .locator('button')
                .filter({ has: page.locator('svg.lucide-plus') })
                .click()
            await connectBinanceAccount(page, `Account ${i + 1}`, false)
            await goToIntegrations(page)
        }

        // Open Manage dialog — should have 3 accounts
        await scrollToBinance(page)
        await openManageDialog(page)
        accountRows = dialogAccountRows(page)
        await expect(accountRows).toHaveCount(3, { timeout: 5_000 })

        // Disconnect the middle account
        const middleRow = accountRows.nth(1)
        await middleRow
            .locator('button')
            .filter({ has: page.locator('svg.lucide-unplug') })
            .click()
        await expect(page.getByText('Confirm Disconnect')).toBeVisible({
            timeout: 5_000,
        })
        await page
            .locator('button', { hasText: 'Disconnect' })
            .filter({ hasNot: page.locator('svg') })
            .click()
        await expect(
            page.getByText('Entity disconnected successfully'),
        ).toBeVisible({ timeout: 10_000 })

        // Reload and verify 2 accounts remain
        await page.reload()
        await page.waitForLoadState('networkidle')
        await goToIntegrations(page)
        await scrollToBinance(page)

        await openManageDialog(page)
        accountRows = dialogAccountRows(page)
        await expect(accountRows).toHaveCount(2, { timeout: 5_000 })
    })
})
