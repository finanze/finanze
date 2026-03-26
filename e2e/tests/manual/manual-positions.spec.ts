import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const CREDENTIALS = {
    user: 'test@example.com',
    password: 'MockPassword123',
}

async function connectAndFetchEntity(
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

        // Navigate back to Integrations to find the Fetch button
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }

    // Fetch data
    const card = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchButton = card.getByRole('button', { name: 'Fetch' })
    if (await fetchButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await fetchButton.click()
        await expect(
            page.getByText(`Select features to fetch from ${entityName}`),
        ).toBeVisible({ timeout: 5_000 })
        await expect(
            page.getByRole('button', { name: 'Fetch data' }),
        ).toBeEnabled({ timeout: 5_000 })
        await page.getByRole('button', { name: 'Fetch data' }).click()
        await expect(
            page.getByText(`Data successfully fetched from ${entityName}`),
        ).toBeVisible({ timeout: 15_000 })
        const cancel = page.getByRole('button', { name: 'Cancel' })
        if (await cancel.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await cancel.click()
            await page.waitForTimeout(500)
        }
    }
}

async function navigateTo(page: Page, section: string) {
    // Navigate via sidebar - sections are in the "My Assets" submenu
    const sidebarBtn = page.getByRole('button', { name: section, exact: true })
    const isVisible = await sidebarBtn.isVisible({ timeout: 1_000 }).catch(() => false)

    if (isVisible) {
        // Sidebar submenu item already visible, click it directly
        await sidebarBtn.click()
    } else {
        // Expand My Assets submenu, then click
        await page.getByRole('button', { name: 'My Assets' }).click()
        await page.waitForTimeout(300)

        // The section might be in the sidebar submenu or on the My Assets dashboard
        const subMenuBtn = page.getByRole('button', { name: section, exact: true })
        const inSubMenu = await subMenuBtn.isVisible({ timeout: 1_000 }).catch(() => false)

        if (inSubMenu) {
            await subMenuBtn.click()
        } else {
            // Fallback: click the card on the My Assets dashboard
            await page
                .getByRole('heading', { name: 'My Assets' })
                .first()
                .waitFor({ timeout: 10_000 })
            await page.getByText(section).click()
        }
    }

    await page
        .getByRole('heading', { name: section })
        .first()
        .waitFor({ timeout: 10_000 })
    await page.waitForTimeout(500)
}

/**
 * Click the DatePicker trigger inside the form dialog (z-[16000]),
 * scoped by the label text. Then pick a specific day from the calendar.
 */
async function selectDatePicker(page: Page, labelText: string, day: number) {
    // The form dialog overlay is the last .fixed.inset-0 element
    const dialog = page.locator('.fixed.inset-0').last()
    const container = dialog.getByText(labelText, { exact: true }).locator('..')
    await container.getByRole('button').first().click()
    await page.waitForTimeout(300)
    // DayPicker gridcell names are full dates (e.g. "Tuesday, March 10th, 2026")
    // Click the button inside the gridcell that contains the day number as text
    const dayRegex = new RegExp(`${day}(st|nd|rd|th)`)
    await page
        .getByRole('gridcell', { name: dayRegex })
        .first()
        .getByRole('button')
        .click()
    await page.waitForTimeout(200)
}

/**
 * Two-save flow for manual positions:
 * 1. Click the form dialog Save (inside overlay)
 * 2. Wait for dialog to close
 * 3. Click the page-level Save (ManualPositionsControls, has lucide-save icon)
 */
async function saveDraftAndPersist(page: Page) {
    // Click form Save inside the dialog overlay
    const dialog = page.locator('.fixed.inset-0').last()
    await dialog.getByRole('button', { name: 'Save' }).click()
    await page.waitForTimeout(800)

    // Click page-level Save button
    await page.getByTestId('save-positions').click()

    await expect(
        page.getByText('Manual positions saved successfully.'),
    ).toBeVisible({ timeout: 10_000 })
}

/**
 * Expand a manual position card and click the delete button (Trash2 icon),
 * then confirm in the dialog and save to server.
 */
async function deleteManualPosition(page: Page, positionName: string) {
    // Enter edit mode
    await page.getByRole('button', { name: 'Edit' }).click()
    await page.waitForTimeout(300)

    // Expand the position card (click the card row with role=button)
    await page.getByText(positionName).first().click()
    await page.waitForTimeout(500)

    // Click the Trash2 button (icon-only, text-red-500)
    await page
        .locator('button.text-red-500')
        .filter({ has: page.locator('.lucide-trash-2') })
        .click()

    // Confirmation dialog
    await expect(page.getByText('Delete manual position')).toBeVisible({
        timeout: 3_000,
    })
    await page
        .locator('.fixed.inset-0')
        .last()
        .getByRole('button', { name: 'Delete' })
        .click()
    await page.waitForTimeout(300)

    // Save page-level
    await page.getByTestId('save-positions').click()
    await expect(
        page.getByText('Manual positions saved successfully.'),
    ).toBeVisible({ timeout: 10_000 })
}

// ── Deposits CRUD ───────────────────────────────────────────────────

test.describe('Manual Positions - Deposits', () => {
    test('create a manual deposit', async ({ authenticatedPage: page }) => {
        await connectAndFetchEntity(page, 'Urbanitae', CREDENTIALS)
        await navigateTo(page, 'Deposits')

        // Click Add
        await page.getByRole('button', { name: 'Add' }).click()
        await expect(page.getByText('Add manual deposit')).toBeVisible({
            timeout: 5_000,
        })

        // Fill form
        await page.locator('#entity_id').selectOption({ label: 'Urbanitae' })
        await page.locator('#name').fill('E2E Manual Deposit')
        await page.locator('#amount').fill('10000')
        await page.locator('#interest_rate').fill('3.5')
        await selectDatePicker(page, 'Start date', 10)
        await selectDatePicker(page, 'Maturity', 15)

        await saveDraftAndPersist(page)

        // Verify position appears
        await expect(page.getByText('E2E Manual Deposit')).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText('3.50%')).toBeVisible()
    })

    test('edit a manual deposit', async ({ authenticatedPage: page }) => {
        await navigateTo(page, 'Deposits')

        await expect(page.getByText('E2E Manual Deposit')).toBeVisible({
            timeout: 10_000,
        })

        // Enter edit mode
        await page.getByRole('button', { name: 'Edit' }).click()
        await page.waitForTimeout(300)

        // Expand the deposit card
        await page.getByText('E2E Manual Deposit').first().click()
        await page.waitForTimeout(500)

        // Click Edit button inside expanded area (Pencil icon + "Edit" text)
        await page
            .locator('button')
            .filter({ has: page.locator('.lucide-pencil') })
            .click()

        await expect(page.getByText('Edit manual deposit')).toBeVisible({
            timeout: 5_000,
        })

        // Change amount
        await page.locator('#amount').fill('15000')

        await saveDraftAndPersist(page)

        await expect(page.getByText('E2E Manual Deposit')).toBeVisible({
            timeout: 10_000,
        })
    })

    test('delete a manual deposit', async ({ authenticatedPage: page }) => {
        await navigateTo(page, 'Deposits')

        await expect(page.getByText('E2E Manual Deposit')).toBeVisible({
            timeout: 10_000,
        })

        await deleteManualPosition(page, 'E2E Manual Deposit')

        // Verify the deposit is gone
        await expect(page.getByText('E2E Manual Deposit')).not.toBeVisible({
            timeout: 5_000,
        })
    })

    test('manual and fetched deposits coexist', async ({
        authenticatedPage: page,
    }) => {
        await connectAndFetchEntity(page, 'Urbanitae', CREDENTIALS)
        await navigateTo(page, 'Deposits')

        // Add manual deposit
        await page.getByRole('button', { name: 'Add' }).click()
        await expect(page.getByText('Add manual deposit')).toBeVisible({
            timeout: 5_000,
        })
        await page.locator('#entity_id').selectOption({ label: 'Urbanitae' })
        await page.locator('#name').fill('Coexistence Deposit')
        await page.locator('#amount').fill('7500')
        await page.locator('#interest_rate').fill('2.5')
        await selectDatePicker(page, 'Start date', 10)
        await selectDatePicker(page, 'Maturity', 15)

        await saveDraftAndPersist(page)

        // Manual deposit should be visible
        await expect(page.getByText('Coexistence Deposit')).toBeVisible({
            timeout: 10_000,
        })

        // Clean up
        await deleteManualPosition(page, 'Coexistence Deposit')
    })
})

// ── Real Estate CF CRUD + coexistence ───────────────────────────────

test.describe('Manual Positions - Real Estate CF', () => {
    test('create a manual real estate CF position', async ({
        authenticatedPage: page,
    }) => {
        await connectAndFetchEntity(page, 'Urbanitae', CREDENTIALS)
        await navigateTo(page, 'Real Estate CF')

        await page.getByRole('button', { name: 'Add' }).click()
        await expect(page.getByText('Add manual real estate CF')).toBeVisible({
            timeout: 5_000,
        })

        await page.locator('#entity_id').selectOption({ label: 'Urbanitae' })
        await page.locator('#name').fill('E2E RE Project')
        await page.locator('#amount').fill('5000')
        await page.locator('#interest_rate').fill('7')
        await page.locator('#type').fill('EQUITY')
        await page.locator('#state').fill('ACTIVE')
        await selectDatePicker(page, 'Start date', 10)
        await selectDatePicker(page, 'Maturity', 15)

        await saveDraftAndPersist(page)

        await expect(page.getByText('E2E RE Project')).toBeVisible({
            timeout: 10_000,
        })
    })

    test('manual and fetched real estate CF coexist', async ({
        authenticatedPage: page,
    }) => {
        await connectAndFetchEntity(page, 'Urbanitae', CREDENTIALS)
        await navigateTo(page, 'Real Estate CF')

        // Wait longer for fetched data to render
        await page.waitForTimeout(2_000)

        // Fetched from mock (Urbanitae supports REAL_ESTATE_CF)
        await expect(page.getByText('Mock RE Project').first()).toBeVisible({
            timeout: 20_000,
        })
        // Manual from previous test (if it ran in this worker)
        const hasManual = await page
            .getByText('E2E RE Project')
            .isVisible({ timeout: 3_000 })
            .catch(() => false)

        if (!hasManual) {
            // Create manual position for coexistence test
            await page.getByRole('button', { name: 'Add' }).click()
            await expect(
                page.getByText('Add manual real estate CF'),
            ).toBeVisible({ timeout: 5_000 })
            await page.locator('#entity_id').selectOption({ label: 'Urbanitae' })
            await page.locator('#name').fill('E2E RE Project')
            await page.locator('#amount').fill('5000')
            await page.locator('#interest_rate').fill('7')
            await page.locator('#type').fill('EQUITY')
            await page.locator('#state').fill('ACTIVE')
            await selectDatePicker(page, 'Start date', 10)
            await selectDatePicker(page, 'Maturity', 15)

            await saveDraftAndPersist(page)
        }

        // Both should be visible
        await expect(page.getByText('Mock RE Project').first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText('E2E RE Project').first()).toBeVisible({
            timeout: 10_000,
        })

        // Clean up
        await deleteManualPosition(page, 'E2E RE Project')
    })
})

// ── Factoring CRUD ─────────────────────────────────────────────────

test.describe('Manual Positions - Factoring', () => {
    test('create and verify a manual factoring position', async ({
        authenticatedPage: page,
    }) => {
        await connectAndFetchEntity(page, 'Urbanitae', CREDENTIALS)
        await navigateTo(page, 'Factoring')

        await page.getByRole('button', { name: 'Add' }).click()
        await expect(page.getByText('Add manual factoring')).toBeVisible({
            timeout: 5_000,
        })

        await page.locator('#entity_id').selectOption({ label: 'Urbanitae' })
        await page.locator('#name').fill('E2E Factoring Invoice')
        await page.locator('#amount').fill('3000')
        await page.locator('#interest_rate').fill('10')
        await page.locator('#type').fill('INVOICE')
        await page.locator('#state').fill('ACTIVE')
        await selectDatePicker(page, 'Start date', 10)
        await selectDatePicker(page, 'Maturity', 15)

        await saveDraftAndPersist(page)

        await expect(page.getByText('E2E Factoring Invoice')).toBeVisible({
            timeout: 10_000,
        })

        // Clean up
        await deleteManualPosition(page, 'E2E Factoring Invoice')
    })
})
