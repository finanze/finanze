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
    }
}

async function navigateToCommodities(page: Page) {
    // Sidebar hides Commodities when there's no data, so navigate via
    // My Assets dashboard → click the Commodities card
    const myAssets = page.getByRole('button', { name: 'My Assets' })
    await myAssets.click()
    await page
        .getByRole('heading', { name: 'My Assets' })
        .first()
        .waitFor({ timeout: 10_000 })
    // Click the Commodities card heading on the dashboard
    await page.getByRole('heading', { name: 'Commodities' }).click()
    await page.waitForTimeout(500)
}

async function saveToServer(page: Page) {
    await page.getByTestId('save-commodities').click()
    await expect(
        page.getByText('Commodities saved successfully'),
    ).toBeVisible({ timeout: 10_000 })
}

async function dismissToasts(page: Page) {
    // Wait for the toast to disappear naturally or dismiss it
    await expect(
        page.getByText('Commodities saved successfully'),
    ).not.toBeVisible({ timeout: 10_000 })
}

async function createCommodity(page: Page, name: string) {
    await page.getByRole('button', { name: 'Add' }).click()
    await expect(page.getByText('Add new entry')).toBeVisible({
        timeout: 5_000,
    })

    await page.locator('#name').fill(name)
    await page.locator('#type').selectOption('GOLD')
    await page.locator('#amount').fill('1')
    await page.locator('#unit').selectOption('TROY_OUNCE')
    await page.locator('#initial_investment').fill('2000')
    await page.locator('#currency').selectOption('EUR')

    const dialog = page.locator('.fixed.inset-0').last()
    await dialog.getByRole('button', { name: 'Add' }).click()
    await page.waitForTimeout(500)

    await saveToServer(page)

    await expect(page.getByText(name)).toBeVisible({
        timeout: 10_000,
    })

    // Dismiss success toast so it doesn't interfere with subsequent interactions
    await dismissToasts(page)
}

test.describe('Manual Commodities', () => {
    test('create a commodity', async ({ authenticatedPage: page }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', CREDENTIALS)
        await navigateToCommodities(page)

        // Empty state should show initially
        await expect(
            page.getByText('No commodities registered'),
        ).toBeVisible({ timeout: 10_000 })

        await createCommodity(page, 'E2E Gold Coin')
    })

    test('edit a commodity', async ({ authenticatedPage: page }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', CREDENTIALS)
        await navigateToCommodities(page)

        // Create a commodity first to ensure self-contained test
        const hasCommodity = await page
            .getByText('E2E Edit Coin')
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!hasCommodity) {
            await createCommodity(page, 'E2E Edit Coin')
        }

        // Find the "E2E Edit Coin" card button and click the three-dot menu inside it
        const editCoinCard = page.getByRole('button', {
            name: /E2E Edit Coin/,
        })
        await expect(editCoinCard).toBeVisible({ timeout: 5_000 })
        // The MoreVertical button is a nested button inside the card
        const moreBtn = editCoinCard.getByRole('button').first()
        await moreBtn.click()
        await page.waitForTimeout(500)

        // Click Edit in the popover (portaled to body) — wait for it to be visible
        const editBtn = page.getByRole('button', { name: 'Edit', exact: true })
        await expect(editBtn).toBeVisible({ timeout: 3_000 })
        await editBtn.click()
        await page.waitForTimeout(500)

        // Edit dialog — change amount (dynamic ID: amount-{id})
        await expect(page.locator('[id^="amount-"]')).toBeVisible({
            timeout: 5_000,
        })
        await page.locator('[id^="amount-"]').fill('2')

        // Click Save in the edit dialog
        const dialog = page.locator('.fixed.inset-0').last()
        await dialog.getByRole('button', { name: 'Save' }).click()
        await page.waitForTimeout(300)

        // Save to server
        await saveToServer(page)
    })

    test('delete a commodity', async ({ authenticatedPage: page }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', CREDENTIALS)
        await navigateToCommodities(page)

        // Create a commodity first to ensure self-contained test
        const hasCommodity = await page
            .getByText('E2E Delete Coin')
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!hasCommodity) {
            await createCommodity(page, 'E2E Delete Coin')
        }

        // Find the "E2E Delete Coin" card button and click the three-dot menu inside it
        const deleteCoinCard = page.getByRole('button', {
            name: /E2E Delete Coin/,
        })
        await expect(deleteCoinCard).toBeVisible({ timeout: 5_000 })
        // The MoreVertical button is a nested button inside the card
        const moreBtn = deleteCoinCard.getByRole('button').first()
        await moreBtn.click()
        await page.waitForTimeout(500)

        // Click Delete in popover — wait for it to be visible
        const deleteButton = page.getByRole('button', {
            name: 'Delete',
            exact: true,
        })
        await expect(deleteButton).toBeVisible({ timeout: 3_000 })
        await deleteButton.click()
        await page.waitForTimeout(500)

        // Confirmation dialog at z-[19000]
        await expect(page.getByText('Delete commodity')).toBeVisible({
            timeout: 3_000,
        })

        // Confirm: click the Delete button inside the confirmation dialog
        const confirmDialog = page.locator('.fixed.inset-0').last()
        await confirmDialog.getByRole('button', { name: 'Delete' }).click()
        await page.waitForTimeout(300)

        // Save to server
        await saveToServer(page)

        // Verify the deleted commodity is gone
        await expect(
            page.getByText('E2E Delete Coin'),
        ).not.toBeVisible({ timeout: 10_000 })
    })
})
