import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { selectEntity } from '../../helpers/entity-selector'
import { ensureEditMode } from '../../helpers/edit-mode'

const ENTITY = 'E2E Portfolio Broker'
const ACCOUNT = 'E2E Portfolio Cash'
const PORTFOLIO = 'E2E Main Portfolio'

function formDialog(page: Page) {
    return page.locator('.fixed.inset-0').last()
}

async function openFromMyAssets(page: Page, section: string) {
    const sidebarBtn = page.getByRole('button', { name: section, exact: true })
    if (await sidebarBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await sidebarBtn.click()
    } else {
        await page.getByRole('button', { name: 'My Assets' }).click()
        await expect(
            page.getByRole('heading', { name: 'My Assets', level: 1 }),
        ).toBeVisible({ timeout: 10_000 })
        await page.getByText(section, { exact: true }).first().click()
    }
}

async function navigateToBanking(page: Page) {
    await openFromMyAssets(page, 'Banking')
    await expect(page.getByText('Loans & Credits')).toBeVisible({
        timeout: 10_000,
    })
    await page.waitForTimeout(500)
}

async function navigateToFunds(page: Page) {
    await openFromMyAssets(page, 'Funds')
    await expect(
        page.getByRole('heading', { name: 'Funds', exact: true, level: 1 }),
    ).toBeVisible({ timeout: 10_000 })
    await page.waitForTimeout(500)
}

function accountsSectionHeader(page: Page) {
    return page
        .getByRole('heading', { name: /^Accounts/ })
        .first()
        .locator('..')
        .locator('..')
}

function accountCard(page: Page, name: string) {
    return page.locator('.hover\\:shadow-lg').filter({ hasText: name })
}

async function persistAndExpectSuccess(page: Page) {
    const saveBtn = page.getByTestId('save-positions')
    await expect(saveBtn).toBeVisible({ timeout: 5_000 })
    await expect(saveBtn).toBeEnabled({ timeout: 3_000 })
    await saveBtn.click()
    await expect(
        page.getByText('Manual positions saved successfully.'),
    ).toBeVisible({ timeout: 10_000 })
    await page.waitForTimeout(500)
}

async function confirmDelete(page: Page) {
    await expect(page.getByText('Delete manual position')).toBeVisible({
        timeout: 3_000,
    })
    await formDialog(page).getByRole('button', { name: 'Delete' }).click()
    await page.waitForTimeout(300)
}

async function enterFundsEditMode(page: Page) {
    await page.getByRole('button', { name: 'Edit', exact: true }).click()
    const listHeader = page.getByRole('button', {
        name: 'Existing fund portfolios',
    })
    await expect(listHeader).toBeVisible({ timeout: 5_000 })
    return listHeader
}

async function exitFundsEditMode(page: Page) {
    await page.getByRole('button', { name: 'Cancel', exact: true }).click()
    await expect(
        page.getByRole('button', { name: 'Existing fund portfolios' }),
    ).not.toBeVisible({ timeout: 5_000 })
}

function portfolioRow(page: Page, name: string) {
    return page
        .locator('div')
        .filter({ hasText: name })
        .filter({
            has: page.getByRole('button', { name: 'Edit draft portfolio' }),
        })
        .last()
}

async function openPortfolioForm(page: Page, name: string) {
    const listHeader = await enterFundsEditMode(page)
    await listHeader.click()
    await page.waitForTimeout(300)
    await portfolioRow(page, name)
        .getByRole('button', { name: 'Edit draft portfolio' })
        .click()
    const dialog = formDialog(page)
    await expect(dialog.getByText('Edit fund portfolio')).toBeVisible({
        timeout: 5_000,
    })
    return dialog
}

async function closePortfolioForm(page: Page) {
    await formDialog(page).getByRole('button', { name: 'Cancel' }).click()
    await expect(page.getByText('Edit fund portfolio')).not.toBeVisible({
        timeout: 5_000,
    })
    await exitFundsEditMode(page)
}

async function expectPortfolioLinkedTo(page: Page, accountName: string) {
    await navigateToFunds(page)
    const dialog = await openPortfolioForm(page, PORTFOLIO)
    await expect(dialog.locator('#related_account option:checked')).toHaveText(
        accountName,
    )
    await closePortfolioForm(page)
}

test.describe('Manual Fund Portfolios - linked account', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
        await ensureEditMode(page, 'DRAFT')
    })

    test('portfolio keeps its account link across account saves and is unlinked when the account is deleted', async ({
        authenticatedPage: page,
    }) => {
        await navigateToBanking(page)
        await accountsSectionHeader(page)
            .locator('button')
            .filter({ has: page.locator('.lucide-plus') })
            .click()
        let dialog = formDialog(page)
        await expect(dialog.getByText('Add an account')).toBeVisible({
            timeout: 5_000,
        })
        await dialog.getByRole('button', { name: 'Create entity' }).click()
        await page.waitForTimeout(200)
        await dialog.locator('#new_entity_name').fill(ENTITY)
        await dialog.locator('#type').selectOption('FUND_PORTFOLIO')
        await dialog.locator('#name').fill(ACCOUNT)
        await dialog.locator('#total').fill('1000')
        await dialog.getByRole('button', { name: 'Save' }).click()
        await page.waitForTimeout(800)
        await persistAndExpectSuccess(page)
        await expect(accountCard(page, ACCOUNT)).toBeVisible({
            timeout: 5_000,
        })

        await navigateToFunds(page)
        const listHeader = await enterFundsEditMode(page)
        await listHeader
            .locator('..')
            .getByRole('button', { name: 'Add', exact: true })
            .click()
        dialog = formDialog(page)
        await expect(dialog.getByText('Add fund portfolio')).toBeVisible({
            timeout: 5_000,
        })
        await selectEntity(page, ENTITY, { inDialog: true })
        await dialog.locator('#name').fill(PORTFOLIO)
        await dialog
            .locator('#related_account')
            .selectOption({ label: ACCOUNT })
        await dialog.getByRole('button', { name: 'Save' }).click()
        await page.waitForTimeout(800)
        await persistAndExpectSuccess(page)

        await expectPortfolioLinkedTo(page, ACCOUNT)

        await navigateToBanking(page)
        await accountsSectionHeader(page)
            .locator('button')
            .filter({ has: page.locator('.lucide-pencil') })
            .click()
        await page.waitForTimeout(300)
        await accountCard(page, ACCOUNT)
            .getByRole('button', { name: 'Edit', exact: true })
            .click()
        dialog = formDialog(page)
        await expect(dialog.getByText('Edit bank account')).toBeVisible({
            timeout: 5_000,
        })
        await dialog.locator('#total').fill('2500')
        await dialog.getByRole('button', { name: 'Save' }).click()
        await page.waitForTimeout(800)
        await persistAndExpectSuccess(page)

        await expectPortfolioLinkedTo(page, ACCOUNT)

        await navigateToBanking(page)
        await accountsSectionHeader(page)
            .locator('button')
            .filter({ has: page.locator('.lucide-pencil') })
            .click()
        await page.waitForTimeout(300)
        await accountCard(page, ACCOUNT)
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        await expect(
            page.getByText(
                "There's 1 manual fund portfolio linked to this account.",
                { exact: false },
            ),
        ).toBeVisible({ timeout: 3_000 })
        await confirmDelete(page)
        await persistAndExpectSuccess(page)
        await expect(accountCard(page, ACCOUNT)).not.toBeVisible({
            timeout: 5_000,
        })

        await navigateToFunds(page)
        dialog = await openPortfolioForm(page, PORTFOLIO)
        await expect(dialog.locator('#related_account')).toHaveCount(0)
        await expect(
            dialog.getByText(
                'Link a fund portfolio account to see its balance alongside your funds.',
            ),
        ).toBeVisible()
        await formDialog(page).getByRole('button', { name: 'Cancel' }).click()
        await expect(page.getByText('Edit fund portfolio')).not.toBeVisible({
            timeout: 5_000,
        })

        await portfolioRow(page, PORTFOLIO)
            .getByRole('button', { name: 'Remove draft portfolio' })
            .click()
        await confirmDelete(page)
        await persistAndExpectSuccess(page)
    })
})
