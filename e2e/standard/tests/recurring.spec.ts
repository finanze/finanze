import { expect, type Page } from '@playwright/test'
import { test } from '../fixtures/auth'
import { navigateToMyMoneyPage } from '../helpers/my-money'

function ordinal(day: number): string {
    const remainder = day % 100
    if (remainder >= 11 && remainder <= 13) return `${day}th`
    switch (day % 10) {
        case 1:
            return `${day}st`
        case 2:
            return `${day}nd`
        case 3:
            return `${day}rd`
        default:
            return `${day}th`
    }
}

async function selectTodayAsSinceDate(page: Page) {
    const dialog = page.locator('.fixed.inset-0').last()
    const sinceField = dialog
        .locator('label')
        .filter({ hasText: /^Since/ })
        .locator('..')
    await sinceField.getByRole('button').click()

    const calendar = page.locator('[data-radix-popper-content-wrapper]').last()
    await expect(calendar).toBeVisible()

    const today = new Date()
    const targetMonth = new Intl.DateTimeFormat('en-US', {
        month: 'long',
        year: 'numeric',
    }).format(today)
    await expect(calendar.getByText(targetMonth, { exact: true })).toBeVisible()

    const monthName = new Intl.DateTimeFormat('en-US', {
        month: 'long',
    }).format(today)
    const dayName = new RegExp(
        `${monthName}\\s+${ordinal(today.getDate())},\\s+${today.getFullYear()}`,
    )
    const dayCell = calendar.getByRole('gridcell', { name: dayName })
    await expect(dayCell).toBeVisible()
    await dayCell.getByRole('button').click()
}

test.describe('Recurring money', () => {
    test('shows compact KPI cards in two columns on mobile', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 390, height: 844 })
        await page
            .getByRole('button', { name: 'My Money', exact: true })
            .click()
        await expect(page).toHaveURL(/\/management$/)
        await page
            .getByRole('heading', { name: 'Recurring', exact: true })
            .click()
        await expect(page).toHaveURL(/\/management\/recurring$/)

        const earnings = page.getByTestId('recurring-kpi-earnings')
        const expenses = page.getByTestId('recurring-kpi-expenses')
        const expenseAmount = page.getByTestId('recurring-expense-amount')
        const expenseRate = page.getByTestId('recurring-expense-rate')
        const savings = page.getByTestId('recurring-kpi-savings')
        const savableTitle = savings.getByTestId('recurring-savable-title')
        const savableAmount = page.getByTestId('recurring-savable-amount')
        const savableRate = page.getByTestId('recurring-savable-rate')
        const savingsCells = savings.locator(':scope > div')
        const investedTitle = savings.getByTestId('recurring-invested-title')
        const investedAmount = savings.getByTestId('recurring-invested-amount')
        await expect(earnings).toBeVisible()
        await expect(expenses).toBeVisible()
        await expect(earnings).not.toContainText(/\d+\s+earnings?/i)
        await expect(expenses).not.toContainText(/\d+\s+expenses?/i)
        await expect(savings).toBeVisible()
        await expect(savingsCells).toHaveCount(2)

        const earningsBox = await earnings.boundingBox()
        const expensesBox = await expenses.boundingBox()
        const expenseAmountBox = await expenseAmount.boundingBox()
        const savableTitleBox = await savableTitle.boundingBox()
        const savableAmountBox = await savableAmount.boundingBox()
        const savableRateBox = await savableRate.boundingBox()
        const investedTitleBox = await investedTitle.boundingBox()
        const investedAmountBox = await investedAmount.boundingBox()
        const savingsBox = await savings.boundingBox()
        const savableBox = await savingsCells.nth(0).boundingBox()
        const investedBox = await savingsCells.nth(1).boundingBox()
        expect(earningsBox).not.toBeNull()
        expect(expensesBox).not.toBeNull()
        expect(expenseAmountBox).not.toBeNull()
        expect(savableTitleBox).not.toBeNull()
        expect(savableAmountBox).not.toBeNull()
        expect(savableRateBox).not.toBeNull()
        expect(investedTitleBox).not.toBeNull()
        expect(investedAmountBox).not.toBeNull()
        expect(savingsBox).not.toBeNull()
        expect(savableBox).not.toBeNull()
        expect(investedBox).not.toBeNull()
        expect(expensesBox!.x).toBeGreaterThan(earningsBox!.x)
        expect(expenseAmountBox!.width).toBeGreaterThan(
            expensesBox!.width * 0.8,
        )
        expect(savableRateBox!.y).toBeLessThan(
            savableAmountBox!.y + savableAmountBox!.height,
        )
        expect(
            await savableAmount.evaluate(
                (element) => element.scrollWidth <= element.clientWidth,
            ),
        ).toBe(true)
        if ((await expenseRate.count()) > 0) {
            const expenseRateBox = await expenseRate.boundingBox()
            expect(expenseRateBox).not.toBeNull()
            expect(expenseRateBox!.y).toBeLessThan(
                expenseAmountBox!.y + expenseAmountBox!.height,
            )
            expect(
                await expenseAmount.evaluate(
                    (element) => element.scrollWidth <= element.clientWidth,
                ),
            ).toBe(true)
        }
        expect(investedBox!.x).toBeGreaterThan(savableBox!.x)
        expect(investedAmountBox!.x - investedBox!.x).toBeCloseTo(12, 0)
        await expect(savings.locator('button[aria-pressed]')).toHaveCount(0)
        await expect
            .poll(async () => {
                const savableBox = await savableTitle.boundingBox()
                const investedBox = await investedTitle.boundingBox()
                return savableBox && investedBox
                    ? Math.abs(savableBox.y - investedBox.y)
                    : Number.POSITIVE_INFINITY
            })
            .toBeLessThan(1)
        await expect
            .poll(async () => {
                const savableBox = await savableAmount.boundingBox()
                const investedBox = await investedAmount.boundingBox()
                return savableBox && investedBox
                    ? Math.abs(savableBox.y - investedBox.y)
                    : Number.POSITIVE_INFINITY
            })
            .toBeLessThan(1)
        expect(savingsBox!.y).toBeGreaterThan(
            Math.max(earningsBox!.y, expensesBox!.y),
        )
    })

    test('keeps icon search unfocused when opened on mobile', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 390, height: 844 })
        await page
            .getByRole('button', { name: 'My Money', exact: true })
            .click()
        await expect(page).toHaveURL(/\/management$/)
        await page
            .getByRole('heading', { name: 'Recurring', exact: true })
            .click()
        await expect(page).toHaveURL(/\/management\/recurring$/)
        await page.getByRole('tab', { name: /Earnings/ }).click()

        const earningsHeading = page.getByRole('heading', {
            name: 'Earnings',
            exact: true,
        })
        await earningsHeading.locator('../..').getByRole('button').click()

        const flowDialog = page.locator('.fixed.inset-0').last()
        const iconPickerTrigger = flowDialog
            .getByText('Icon', { exact: true })
            .locator('..')
            .getByRole('button', { name: 'Select an icon' })
        await iconPickerTrigger.click()

        const searchInput = page.getByPlaceholder('Search for an icon...')
        await expect(searchInput).toBeVisible()
        await expect(searchInput).not.toBeFocused()
        await searchInput.focus()
        await expect(searchInput).toBeFocused()
    })

    test('creates, edits, and deletes a recurring earning', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToMyMoneyPage(page, 'Recurring')
        await expect(
            page.getByRole('heading', { name: /^Recurring/ }),
        ).toBeVisible()
        await page.getByRole('tab', { name: /Earnings/ }).click()
        const earningsTab = page.getByRole('tab', { name: /^Earnings/ })
        const earningsTabCount = earningsTab
            .locator('span')
            .filter({ hasText: /^\d+$/ })
        const initialEarningsCount = Number(await earningsTabCount.innerText())

        const earningsHeading = page.getByRole('heading', {
            name: 'Earnings',
            exact: true,
        })
        await earningsHeading.locator('../..').getByRole('button').click()

        const flowDialog = page.locator('.fixed.inset-0').last()
        const monthlyFrequency = flowDialog.getByTestId(
            'recurring-frequency-option-monthly',
        )
        await expect(monthlyFrequency).toHaveAttribute('aria-pressed', 'true')
        await expect(monthlyFrequency).toHaveCSS('min-height', '32px')
        await expect(monthlyFrequency).toHaveCSS('padding-left', '8px')
        await expect(monthlyFrequency).toHaveClass(/bg-neutral-900/)
        await expect(monthlyFrequency).toHaveClass(/dark:bg-white/)
        await flowDialog.getByTestId('recurring-frequency-more').click()
        await expect(
            flowDialog.getByTestId('recurring-frequency-option-semimonthly'),
        ).toHaveCount(0)
        await expect(
            flowDialog.getByTestId(
                'recurring-frequency-option-every_two_months',
            ),
        ).toHaveCount(0)
        const createdFlowName = 'E2E Recurring CRUD Flow'
        const updatedFlowName = 'E2E Recurring CRUD Flow Edited'
        const fields = flowDialog.getByRole('textbox')
        await fields.nth(0).fill(createdFlowName)
        await fields.nth(1).fill('83.50')
        await selectTodayAsSinceDate(page)
        await flowDialog
            .getByRole('button', { name: 'Save', exact: true })
            .click()
        await expect(flowDialog).toBeHidden()
        await expect(earningsTabCount).toHaveText(
            String(initialEarningsCount + 1),
        )

        const createdHeading = page.getByRole('heading', {
            name: createdFlowName,
            exact: true,
        })
        await expect(createdHeading).toBeVisible()
        let flowHeader = page
            .locator('div[role="button"][aria-expanded]')
            .filter({ has: createdHeading })
        if ((await flowHeader.getAttribute('aria-expanded')) !== 'true') {
            await flowHeader.click()
        }

        let flowActions = flowHeader
            .locator('..')
            .locator('[data-no-expand]')
            .getByRole('button')
        await expect(flowActions).toHaveCount(2)
        await flowActions.nth(0).click()

        const editDialog = page.locator('.fixed.inset-0').last()
        await editDialog.getByRole('textbox').nth(0).fill(updatedFlowName)
        await editDialog.getByRole('switch').click()
        await editDialog
            .getByRole('button', { name: 'Save', exact: true })
            .click()
        await expect(editDialog).toBeHidden()
        await expect(earningsTabCount).toHaveText(String(initialEarningsCount))
        await expect(createdHeading).toHaveCount(0)

        const updatedHeading = page.getByRole('heading', {
            name: updatedFlowName,
        })
        await expect(updatedHeading).toBeVisible()
        flowHeader = page
            .locator('div[role="button"][aria-expanded]')
            .filter({ has: updatedHeading })
        if ((await flowHeader.getAttribute('aria-expanded')) !== 'true') {
            await flowHeader.click()
        }

        flowActions = flowHeader
            .locator('..')
            .locator('[data-no-expand]')
            .getByRole('button')
        await expect(flowActions).toHaveCount(2)
        await flowActions.nth(1).click()

        const confirmation = page.locator('.fixed.inset-0').last()
        await confirmation
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        await expect(updatedHeading).toHaveCount(0)
        await expect(earningsTabCount).toHaveText(String(initialEarningsCount))
    })
})
