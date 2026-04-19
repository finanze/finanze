import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { selectEntity } from '../../helpers/entity-selector'

async function navigateToBanking(page: Page) {
    const sidebarBtn = page.getByRole('button', {
        name: 'Banking',
        exact: true,
    })
    const isVisible = await sidebarBtn
        .isVisible({ timeout: 1_000 })
        .catch(() => false)

    if (isVisible) {
        await sidebarBtn.click()
    } else {
        await page.getByRole('button', { name: 'My Assets' }).click()
        await page.waitForTimeout(300)
        await page.getByRole('button', { name: 'Banking', exact: true }).click()
    }

    await expect(page.getByText('Loans & Credits')).toBeVisible({
        timeout: 10_000,
    })
    await page.waitForTimeout(500)
}

function loansSectionHeader(page: Page) {
    return page.getByText('Loans & Credits').locator('..').locator('..')
}

async function openCreditForm(page: Page) {
    await loansSectionHeader(page)
        .locator('button')
        .filter({ has: page.locator('.lucide-plus') })
        .click()
    await page.waitForTimeout(300)
    await page.getByRole('button', { name: 'Credit', exact: true }).click()
    await page.waitForTimeout(500)
}

async function fillCreditForm(
    page: Page,
    fields: {
        newEntityName?: string
        name: string
        creditLimit: string
        drawnAmount: string
        interestRate: string
        pledgedAmount?: string
    },
) {
    const dialog = page.locator('.fixed.inset-0').last()

    if (fields.newEntityName) {
        await dialog.getByRole('button', { name: 'Create entity' }).click()
        await page.waitForTimeout(200)
        await dialog.locator('#new_entity_name').fill(fields.newEntityName)
    }

    await dialog.locator('#name').fill(fields.name)
    await dialog.locator('#credit_limit').fill(fields.creditLimit)
    await dialog.locator('#drawn_amount').fill(fields.drawnAmount)
    await dialog.locator('#interest_rate').fill(fields.interestRate)
    if (fields.pledgedAmount) {
        await dialog.locator('#pledged_amount').fill(fields.pledgedAmount)
    }

    await dialog.getByRole('button', { name: 'Save' }).click()
    await page.waitForTimeout(800)
}

function creditCard(page: Page, name: string) {
    return page.locator('.hover\\:shadow-lg').filter({ hasText: name })
}

async function persistAndExpectSuccess(page: Page) {
    await page
        .locator('button')
        .filter({ has: page.locator('.lucide-save') })
        .click()
    await expect(
        page.getByText('Manual positions saved successfully.'),
    ).toBeVisible({ timeout: 10_000 })
    await page.waitForTimeout(500)
}

async function enterEditMode(page: Page) {
    await loansSectionHeader(page)
        .locator('button')
        .filter({ has: page.locator('.lucide-pencil') })
        .click()
    await page.waitForTimeout(300)
}

async function deleteCredit(page: Page, name: string) {
    const card = creditCard(page, name)
    await card.getByRole('button', { name: 'Delete' }).click()

    await expect(page.getByText('Delete manual position')).toBeVisible({
        timeout: 3_000,
    })
    await page
        .locator('.fixed.inset-0')
        .last()
        .getByRole('button', { name: 'Delete' })
        .click()
    await page.waitForTimeout(300)

    await persistAndExpectSuccess(page)
    await expect(creditCard(page, name)).not.toBeVisible({ timeout: 5_000 })
}

test.describe('Manual Credits - Banking', () => {
    test('create a manual credit with a new entity, verify draft and saved state, then delete', async ({
        authenticatedPage: page,
    }) => {
        await navigateToBanking(page)
        await openCreditForm(page)

        const dialog = page.locator('.fixed.inset-0').last()
        await expect(dialog.getByText('Add a credit line')).toBeVisible({
            timeout: 5_000,
        })

        await fillCreditForm(page, {
            newEntityName: 'Test Credit Entity',
            name: 'Test Credit Line',
            creditLimit: '10000',
            drawnAmount: '3000',
            interestRate: '5.5',
            pledgedAmount: '2000',
        })

        // ── Verify draft state ──────────────────────────────────────
        const card = creditCard(page, 'Test Credit Line')
        await expect(card).toBeVisible({ timeout: 5_000 })
        await expect(card).toHaveClass(/ring-blue-400/, { timeout: 3_000 })
        await expect(card.getByText('You have unsaved changes')).toBeVisible()

        // ── Persist to server ───────────────────────────────────────
        await persistAndExpectSuccess(page)

        // ── Verify persisted credit card content ────────────────────
        const saved = creditCard(page, 'Test Credit Line')
        await expect(saved).toBeVisible({ timeout: 5_000 })
        await expect(saved.getByText('Credit', { exact: true })).toBeVisible()
        await expect(saved.getByText('Test Credit Entity')).toBeVisible()
        await expect(saved.getByText('Drawn Amount')).toBeVisible()
        await expect(saved.getByText('€3,000.00').first()).toBeVisible()
        await expect(saved.getByText('Credit Limit')).toBeVisible()
        await expect(saved.getByText('€10,000.00')).toBeVisible()
        await expect(saved.getByText('Interest Rate')).toBeVisible()
        await expect(saved.getByText(/5[.,]5\s*%/).first()).toBeVisible()
        await expect(
            saved.getByText('Available', { exact: true }),
        ).toBeVisible()
        await expect(saved.getByText('€7,000.00')).toBeVisible()
        await expect(saved.getByText('Pledged guarantees value')).toBeVisible()
        await expect(saved.getByText('€2,000.00')).toBeVisible()
        await expect(saved.getByText('Utilization')).toBeVisible()
        await expect(saved.getByText('30.0%')).toBeVisible()
        await expect(saved).not.toHaveClass(/ring-blue-400/)

        // ── Cleanup ─────────────────────────────────────────────────
        await enterEditMode(page)
        await deleteCredit(page, 'Test Credit Line')
    })

    test('edit a credit while still in draft (before saving to server)', async ({
        authenticatedPage: page,
    }) => {
        await navigateToBanking(page)
        await openCreditForm(page)

        await fillCreditForm(page, {
            newEntityName: 'Draft Edit Entity',
            name: 'Draft Credit',
            creditLimit: '5000',
            drawnAmount: '1000',
            interestRate: '3',
        })

        const card = creditCard(page, 'Draft Credit')
        await expect(card).toBeVisible({ timeout: 5_000 })
        await expect(card).toHaveClass(/ring-blue-400/, { timeout: 3_000 })

        // ── Edit the draft credit ───────────────────────────────────
        await card.getByRole('button', { name: 'Edit' }).click()
        await page.waitForTimeout(500)

        const editDialog = page.locator('.fixed.inset-0').last()
        await expect(editDialog.getByText('Edit manual credit')).toBeVisible({
            timeout: 5_000,
        })

        // Switch entity from "new" mode to "select" mode since it was already created
        await editDialog
            .getByRole('button', { name: 'Cancel new entity' })
            .click()
        await page.waitForTimeout(200)
        await selectEntity(page, 'Draft Edit Entity', { inDialog: true })

        await editDialog.locator('#name').fill('Draft Credit Edited')
        await editDialog.locator('#credit_limit').fill('8000')
        await editDialog.locator('#drawn_amount').fill('2000')
        await editDialog.locator('#interest_rate').fill('4.25')

        await editDialog.getByRole('button', { name: 'Save' }).click()
        await page.waitForTimeout(800)

        // ── Verify the edited draft card ────────────────────────────
        const edited = creditCard(page, 'Draft Credit Edited')
        await expect(edited).toBeVisible({ timeout: 5_000 })
        await expect(edited).toHaveClass(/ring-blue-400/, { timeout: 3_000 })
        await expect(edited.getByText('You have unsaved changes')).toBeVisible()

        // Values should reflect edits
        await expect(edited.getByText('€2,000.00').first()).toBeVisible()
        await expect(edited.getByText('€8,000.00')).toBeVisible()
        await expect(edited.getByText(/4[.,]25\s*%/).first()).toBeVisible()
        await expect(edited.getByText('€6,000.00')).toBeVisible()

        // ── Persist and verify ──────────────────────────────────────
        await persistAndExpectSuccess(page)

        const saved = creditCard(page, 'Draft Credit Edited')
        await expect(saved).toBeVisible({ timeout: 5_000 })
        await expect(saved).not.toHaveClass(/ring-blue-400/)
        await expect(saved.getByText('Draft Edit Entity')).toBeVisible()

        // ── Cleanup ─────────────────────────────────────────────────
        await enterEditMode(page)
        await deleteCredit(page, 'Draft Credit Edited')
    })

    test('edit a saved credit and re-save', async ({
        authenticatedPage: page,
    }) => {
        await navigateToBanking(page)

        // ── Create and persist a credit ─────────────────────────────
        await openCreditForm(page)
        await fillCreditForm(page, {
            newEntityName: 'Saved Edit Entity',
            name: 'Saved Credit',
            creditLimit: '20000',
            drawnAmount: '5000',
            interestRate: '6',
        })
        await persistAndExpectSuccess(page)

        const saved = creditCard(page, 'Saved Credit')
        await expect(saved).toBeVisible({ timeout: 5_000 })
        await expect(saved).not.toHaveClass(/ring-blue-400/)

        // ── Enter edit mode and click Edit on the card ──────────────
        await enterEditMode(page)

        const card = creditCard(page, 'Saved Credit')
        await card.getByRole('button', { name: 'Edit' }).click()
        await page.waitForTimeout(500)

        const editDialog = page.locator('.fixed.inset-0').last()
        await expect(editDialog.getByText('Edit manual credit')).toBeVisible({
            timeout: 5_000,
        })

        // ── Modify values ───────────────────────────────────────────
        await editDialog.locator('#name').fill('Saved Credit Updated')
        await editDialog.locator('#credit_limit').fill('25000')
        await editDialog.locator('#drawn_amount').fill('10000')
        await editDialog.locator('#interest_rate').fill('7')
        await editDialog.locator('#pledged_amount').fill('5000')

        await editDialog.getByRole('button', { name: 'Save' }).click()
        await page.waitForTimeout(800)

        // ── Verify dirty state ──────────────────────────────────────
        const dirty = creditCard(page, 'Saved Credit Updated')
        await expect(dirty).toBeVisible({ timeout: 5_000 })
        await expect(dirty).toHaveClass(/ring-blue-400/, { timeout: 3_000 })
        await expect(dirty.getByText('You have unsaved changes')).toBeVisible()

        // ── Persist edits ───────────────────────────────────────────
        await persistAndExpectSuccess(page)

        // ── Verify updated persisted card ───────────────────────────
        const updated = creditCard(page, 'Saved Credit Updated')
        await expect(updated).toBeVisible({ timeout: 5_000 })
        await expect(updated).not.toHaveClass(/ring-blue-400/)
        await expect(updated.getByText('Saved Edit Entity')).toBeVisible()
        await expect(updated.getByText('€10,000.00').first()).toBeVisible()
        await expect(updated.getByText('€25,000.00')).toBeVisible()
        await expect(updated.getByText(/7[.,]0?\s*%/).first()).toBeVisible()
        await expect(updated.getByText('€15,000.00')).toBeVisible()
        await expect(
            updated.getByText('Pledged guarantees value'),
        ).toBeVisible()
        await expect(updated.getByText('€5,000.00')).toBeVisible()

        // ── Cleanup ─────────────────────────────────────────────────
        await enterEditMode(page)
        await deleteCredit(page, 'Saved Credit Updated')
    })
})
