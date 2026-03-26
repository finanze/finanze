import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const CREDENTIALS = {
    user: 'test@example.com',
    password: 'MockPassword123',
}

async function connectEntityIfNeeded(
    page: Page,
    entityName: string,
    credentials: Record<string, string>,
) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

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
        ).toBeVisible({ timeout: 15_000 })

        // Navigate back to Integrations to clear the login state
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }

    // Dismiss any lingering dialogs
    const cancelBtn2 = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn2.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await cancelBtn2.click()
        await page.waitForTimeout(500)
    }
}

async function navigateToTransactions(page: Page) {
    // Navigate via sidebar like a real user
    await page.waitForTimeout(500)
    await page.getByRole('button', { name: 'Transactions' }).click()
    await page
        .getByRole('heading', { name: 'Transactions' })
        .first()
        .waitFor({ timeout: 10_000 })
    await page.waitForTimeout(500)
}

/**
 * Select a date in the transaction dialog's DatePicker.
 * Scopes to the dialog overlay to avoid matching page-level date filters.
 */
async function selectTransactionDate(page: Page, day: number) {
    const dialog = page.locator('.fixed.inset-0').last()
    const dateContainer = dialog.getByText('Date', { exact: true }).locator('..')
    await dateContainer.getByRole('button').first().click()
    await page.waitForTimeout(300)
    const dayRegex = new RegExp(`${day}(st|nd|rd|th)`)
    await page
        .getByRole('gridcell', { name: dayRegex })
        .first()
        .getByRole('button')
        .click()
    await page.waitForTimeout(200)
}

async function expandTransaction(page: Page, txName: string) {
    const txRow = page.getByText(txName).first().locator('../..')
    await txRow.getByTestId('expand-tx').click()
    await page.waitForTimeout(500)
}

async function createManualTransaction(page: Page, name: string, amount: string) {
    await page.getByRole('button', { name: 'Add' }).click()
    await expect(page.getByText('Add manual transaction')).toBeVisible({
        timeout: 5_000,
    })

    await page
        .locator('#transaction-entity')
        .selectOption({ label: 'Urbanitae' })
    await page.locator('#transaction-name').fill(name)
    // Keep the default date (today) — no need to pick a specific day
    await page.locator('#transaction-type').selectOption('INTEREST')
    await page.locator('#transaction-amount').fill(amount)
    await page.locator('#transaction-currency').selectOption('EUR')

    const dialog = page.locator('.fixed.inset-0').last()
    await dialog.getByRole('button', { name: 'Save' }).click()

    await expect(
        page.getByText('Manual transaction created successfully'),
    ).toBeVisible({ timeout: 10_000 })
}

test.describe('Manual Transactions', () => {
    test('add a manual transaction', async ({ authenticatedPage: page }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', CREDENTIALS)
        await navigateToTransactions(page)

        await createManualTransaction(page, 'E2E Manual Tx', '500.75')
    })

    test('edit a manual transaction', async ({ authenticatedPage: page }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', CREDENTIALS)
        await navigateToTransactions(page)

        // Create a transaction to edit (self-contained test)
        const hasTx = await page
            .getByText('E2E Edit Tx')
            .first()
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!hasTx) {
            await createManualTransaction(page, 'E2E Edit Tx', '500.75')
            // Wait for the list to refresh after creation (async fetch runs in background)
            await page.waitForTimeout(2_000)
        }

        // If the created transaction still isn't visible, navigate away and back
        const txVisible = await page
            .getByText('E2E Edit Tx')
            .first()
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!txVisible) {
            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 10_000 })
            await navigateToTransactions(page)
        }

        await expect(page.getByText('E2E Edit Tx').first()).toBeVisible({
            timeout: 10_000,
        })

        // Expand the transaction card
        await expandTransaction(page, 'E2E Edit Tx')

        // Wait for Edit button to be visible, then click using accessible name
        await page.getByRole('button', { name: 'Edit' }).click()

        await expect(page.getByText('Edit manual transaction')).toBeVisible({
            timeout: 5_000,
        })

        // Change amount
        await page.locator('#transaction-amount').fill('750.50')

        // Submit
        const dialog = page.locator('.fixed.inset-0').last()
        await dialog.getByRole('button', { name: 'Save' }).click()
        await expect(
            page.getByText('Manual transaction updated successfully'),
        ).toBeVisible({ timeout: 10_000 })

        await expect(page.getByText('E2E Edit Tx').first()).toBeVisible({
            timeout: 5_000,
        })
    })

    test('delete a manual transaction', async ({
        authenticatedPage: page,
    }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', CREDENTIALS)
        await navigateToTransactions(page)

        // Create a transaction to delete (self-contained test)
        const hasTx = await page
            .getByText('E2E Delete Tx')
            .first()
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!hasTx) {
            await createManualTransaction(page, 'E2E Delete Tx', '300.00')
            // Wait for the list to refresh after creation
            await page.waitForTimeout(2_000)
        }

        // If the created transaction still isn't visible, navigate away and back
        const txVisible = await page
            .getByText('E2E Delete Tx')
            .first()
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!txVisible) {
            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 10_000 })
            await navigateToTransactions(page)
        }

        await expect(page.getByText('E2E Delete Tx').first()).toBeVisible({
            timeout: 10_000,
        })

        await expandTransaction(page, 'E2E Delete Tx')

        // Click Delete button using accessible name (scoped after expand)
        await page.getByRole('button', { name: 'Delete' }).click()

        // Confirmation dialog
        await expect(
            page.getByText('Delete manual transaction'),
        ).toBeVisible({ timeout: 3_000 })
        await expect(
            page.getByText(
                'Are you sure you want to delete this manual transaction?',
            ),
        ).toBeVisible()

        // Confirm deletion inside the dialog
        await page
            .locator('.fixed.inset-0')
            .last()
            .getByRole('button', { name: 'Delete' })
            .click()

        await expect(
            page.getByText('Manual transaction deleted successfully'),
        ).toBeVisible({ timeout: 10_000 })

        // Verify gone
        await expect(page.getByText('E2E Delete Tx').first()).not.toBeVisible({
            timeout: 5_000,
        })
    })

    test('decimal amount with dot is handled correctly', async ({
        authenticatedPage: page,
    }) => {
        await navigateToTransactions(page)

        await page.getByRole('button', { name: 'Add' }).click()
        await expect(page.getByText('Add manual transaction')).toBeVisible({
            timeout: 5_000,
        })

        await page
            .locator('#transaction-entity')
            .selectOption({ label: 'Urbanitae' })
        await page.locator('#transaction-name').fill('Decimal Test Tx')
        // Keep the default date (today)
        await page.locator('#transaction-type').selectOption('INTEREST')
        await page.locator('#transaction-amount').fill('1234.56')
        await page.locator('#transaction-currency').selectOption('EUR')

        const dialog = page.locator('.fixed.inset-0').last()
        await dialog.getByRole('button', { name: 'Save' }).click()
        await expect(
            page.getByText('Manual transaction created successfully'),
        ).toBeVisible({ timeout: 10_000 })

        // Verify transaction appears
        await expect(page.getByText('Decimal Test Tx').first()).toBeVisible({
            timeout: 10_000,
        })

        // Expand to verify amount displayed correctly
        await expandTransaction(page, 'Decimal Test Tx')

        // Clean up: delete — click the Delete button in the expanded area
        await page.getByRole('button', { name: 'Delete' }).click()
        await expect(
            page.getByText('Delete manual transaction'),
        ).toBeVisible({ timeout: 3_000 })
        await page
            .locator('.fixed.inset-0')
            .last()
            .getByRole('button', { name: 'Delete' })
            .click()
        await expect(
            page.getByText('Manual transaction deleted successfully'),
        ).toBeVisible({ timeout: 10_000 })
    })
})
