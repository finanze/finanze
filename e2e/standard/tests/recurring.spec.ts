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

async function createBudgetExpense(
    page: Page,
    name: string,
    amount: string,
    category: string,
    labelKey = 'groceries',
) {
    await page.getByRole('tab', { name: /^Expenses/ }).click()
    await page.getByRole('button', { name: 'Add', exact: true }).click()
    const dialog = page.locator('.fixed.inset-0').last()
    await dialog.getByPlaceholder('Enter name').fill(name)
    await dialog.getByRole('textbox').nth(1).fill(amount)
    await dialog.getByPlaceholder('Enter category').fill(category)
    await dialog.getByTestId(`label-option-${labelKey}`).click()
    await selectTodayAsSinceDate(page)
    const saved = page.waitForResponse(
        (response) =>
            new URL(response.url()).pathname.endsWith('/flows/periodic') &&
            response.request().method() === 'POST',
    )
    await dialog.getByRole('button', { name: 'Save', exact: true }).click()
    const request = (await saved).request().postDataJSON() as {
        label_id: string
    }
    await expect(dialog).toBeHidden()
    await expect(page.getByRole('heading', { name, exact: true })).toBeVisible()
    return request.label_id
}

async function deleteBudgetEntry(page: Page, name: string) {
    const heading = page.getByRole('heading', { name, exact: true })
    const header = page
        .locator('div[role="button"][aria-expanded]')
        .filter({ has: heading })
    if ((await header.getAttribute('aria-expanded')) !== 'true')
        await header.click()
    await header
        .locator('..')
        .locator('[data-no-expand]')
        .getByRole('button')
        .nth(1)
        .click()
    await page
        .locator('.fixed.inset-0')
        .last()
        .getByRole('button', { name: 'Delete', exact: true })
        .click()
    await expect(heading).toHaveCount(0)
}

test.describe('Budget', () => {
    test('uses categories before labels for chart groups and entry colors', async ({
        authenticatedPage: page,
    }, testInfo) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToMyMoneyPage(page, 'Budget')
        const first = 'E2E Budget Grocery Base'
        const second = 'E2E Budget Grocery Extras'
        const third = 'E2E Budget Uncategorised Base'
        const fourth = 'E2E Budget Uncategorised Extras'
        const category = 'E2E Budget Basics'
        const labelId = await createBudgetExpense(page, first, '400', category)
        await createBudgetExpense(page, second, '200', category, 'salary')
        await createBudgetExpense(page, third, '120', '')
        await createBudgetExpense(page, fourth, '80', '')
        for (const [width, height] of [
            [1440, 1000],
            [390, 844],
        ]) {
            await page.setViewportSize({ width, height })
            await page.getByRole('tab', { name: /^Overview/ }).click()
            await expect(
                page.getByTestId('recurring-category-select'),
            ).toHaveCount(0)
            const categoryGroup = page.getByTestId(
                `budget-category-expense-${category}`,
            )
            const labelGroup = page.getByTestId(
                `budget-label-expense-${labelId}`,
            )
            await expect(categoryGroup).toHaveCount(1)
            await expect(categoryGroup).toContainText(/600[.,]?00/)
            await expect(labelGroup).toHaveCount(1)
            await expect(labelGroup).toContainText(/200[.,]?00/)
            const categoryColor = await categoryGroup
                .locator('div')
                .first()
                .evaluate(
                    (element) => getComputedStyle(element).backgroundColor,
                )
            const labelColor = await labelGroup
                .locator('div')
                .first()
                .evaluate(
                    (element) => getComputedStyle(element).backgroundColor,
                )
            await page.screenshot({
                path: testInfo.outputPath(`budget-overview-${width}.png`),
                fullPage: true,
            })
            await categoryGroup.click()
            await expect(
                page.getByRole('tab', { name: /^Expenses/ }),
            ).toHaveAttribute('aria-selected', 'true')
            await expect(
                page.getByTestId('recurring-category-filter'),
            ).toContainText(category)
            await expect(
                page.getByTestId('recurring-label-filter'),
            ).toHaveCount(0)
            await expect(
                page.getByRole('heading', { name: first, exact: true }),
            ).toBeVisible()
            await expect(
                page.getByRole('heading', { name: second, exact: true }),
            ).toBeVisible()
            await expect(
                page.getByRole('heading', { name: third, exact: true }),
            ).toHaveCount(0)
            const firstHeader = page
                .locator('div[role="button"][aria-expanded]')
                .filter({
                    has: page.getByRole('heading', {
                        name: first,
                        exact: true,
                    }),
                })
            const secondHeader = page
                .locator('div[role="button"][aria-expanded]')
                .filter({
                    has: page.getByRole('heading', {
                        name: second,
                        exact: true,
                    }),
                })
            const groceriesChipColor = await firstHeader
                .getByTestId('label-chip')
                .evaluate((element) => getComputedStyle(element).color)
            expect(
                await firstHeader
                    .getByRole('button', { name: category, exact: true })
                    .evaluate((element) =>
                        element.nextElementSibling?.getAttribute('data-testid'),
                    ),
            ).toBe('label-chip')
            for (const header of [firstHeader, secondHeader]) {
                expect(
                    await header
                        .locator('..')
                        .evaluate(
                            (element) =>
                                getComputedStyle(element).borderLeftColor,
                        ),
                ).toBe(categoryColor)
            }
            await page
                .getByTestId('recurring-category-filter')
                .getByRole('button', { name: 'Clear', exact: true })
                .click()
            await page.getByRole('tab', { name: /^Overview/ }).click()
            await labelGroup.click()
            await expect(
                page.getByTestId('recurring-label-filter'),
            ).toContainText('Groceries')
            await expect(
                page.getByRole('heading', { name: third, exact: true }),
            ).toBeVisible()
            await expect(
                page.getByRole('heading', { name: fourth, exact: true }),
            ).toBeVisible()
            await expect(
                page.getByRole('heading', { name: first, exact: true }),
            ).toHaveCount(0)
            const thirdHeader = page
                .locator('div[role="button"][aria-expanded]')
                .filter({
                    has: page.getByRole('heading', {
                        name: third,
                        exact: true,
                    }),
                })
            expect(
                await thirdHeader
                    .locator('..')
                    .evaluate(
                        (element) => getComputedStyle(element).borderLeftColor,
                    ),
            ).toBe(labelColor)
            expect(
                await thirdHeader
                    .getByTestId('label-chip')
                    .evaluate((element) => getComputedStyle(element).color),
            ).toBe(groceriesChipColor)
            await page.getByTestId('recurring-label-filter').click()
            const earnings = await page
                .getByTestId('recurring-kpi-earnings')
                .innerText()
            const expenses = await page
                .getByTestId('recurring-kpi-expenses')
                .innerText()
            await page.getByTestId('recurring-category-select').click()
            await page
                .getByTestId('recurring-category-option-E2E Budget Basics')
                .getByRole('button', {
                    name: 'Include category: E2E Budget Basics',
                    exact: true,
                })
                .click()
            await page.getByTestId('recurring-category-select').click()
            await expect(
                page.getByRole('heading', { name: first, exact: true }),
            ).toBeVisible()
            await expect(
                page.getByRole('heading', { name: second, exact: true }),
            ).toBeVisible()
            await expect(
                page.getByRole('heading', { name: third, exact: true }),
            ).toHaveCount(0)
            await expect(page.getByTestId('recurring-kpi-earnings')).toHaveText(
                earnings,
                { useInnerText: true },
            )
            await expect(page.getByTestId('recurring-kpi-expenses')).toHaveText(
                expenses,
                { useInnerText: true },
            )
            await expect(
                page.getByTestId('recurring-kpi-savings'),
            ).toBeVisible()
            await page.getByTestId('recurring-invested-title').click()
            await expect(
                page.getByRole('tab', { name: /^Investments/ }),
            ).toHaveAttribute('aria-selected', 'true')
            await expect(
                page.getByTestId('recurring-category-select'),
            ).toHaveCount(0)
            const overflow = await page.evaluate(
                () => document.documentElement.scrollWidth > window.innerWidth,
            )
            expect(overflow).toBe(false)
        }
        await page.getByRole('tab', { name: /^Expenses/ }).click()
        await page
            .getByTestId('recurring-category-filter')
            .getByRole('button', { name: 'Clear', exact: true })
            .click()
        await deleteBudgetEntry(page, first)
        await deleteBudgetEntry(page, second)
        await deleteBudgetEntry(page, third)
        await deleteBudgetEntry(page, fourth)
    })

    test('shows compact KPI cards in two columns on mobile', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 390, height: 844 })
        await page
            .getByRole('button', { name: 'My Money', exact: true })
            .click()
        await expect(page).toHaveURL(/\/management$/)
        await page.getByRole('heading', { name: 'Budget', exact: true }).click()
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
        await page.getByRole('heading', { name: 'Budget', exact: true }).click()
        await expect(page).toHaveURL(/\/management\/recurring$/)
        await page.getByRole('tab', { name: /Earnings/ }).click()

        await page.getByRole('button', { name: 'Add', exact: true }).click()

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
        await navigateToMyMoneyPage(page, 'Budget')
        await expect(
            page.getByRole('heading', { name: /^Budget/ }),
        ).toBeVisible()
        await page.getByRole('tab', { name: /Earnings/ }).click()
        const earningsTab = page.getByRole('tab', { name: /^Earnings/ })
        const earningsTabCount = earningsTab
            .locator('span')
            .filter({ hasText: /^\d+$/ })
        const initialEarningsCount = Number(await earningsTabCount.innerText())

        await page.getByRole('button', { name: 'Add', exact: true }).click()

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
        await flowDialog
            .getByPlaceholder('Enter category')
            .fill('E2E Household')
        const labelOptions = flowDialog
            .getByTestId('label-selector')
            .getByRole('button')
        const firstLabelName = (await labelOptions.nth(0).innerText()).trim()
        await labelOptions.nth(0).click()
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
        await expect(flowHeader.getByTestId('label-chip')).toHaveText(
            firstLabelName,
        )
        await expect(flowHeader).toContainText('E2E Household')
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
        const editLabelOptions = editDialog
            .getByTestId('label-selector')
            .getByRole('button')
        await expect(editLabelOptions.nth(0)).toHaveAttribute(
            'aria-pressed',
            'true',
        )
        const secondLabelName = (
            await editLabelOptions.nth(1).innerText()
        ).trim()
        await editLabelOptions.nth(1).click()
        await expect(editLabelOptions.nth(0)).toHaveAttribute(
            'aria-pressed',
            'false',
        )
        await expect(editLabelOptions.nth(1)).toHaveAttribute(
            'aria-pressed',
            'true',
        )
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
        await expect(flowHeader.getByTestId('label-chip')).toHaveText(
            secondLabelName,
        )
        await expect(flowHeader).toContainText('E2E Household')
        if ((await flowHeader.getAttribute('aria-expanded')) !== 'true') {
            await flowHeader.click()
        }

        flowActions = flowHeader
            .locator('..')
            .locator('[data-no-expand]')
            .getByRole('button')
        await expect(flowActions).toHaveCount(2)
        await flowActions.nth(0).click()
        const clearDialog = page.locator('.fixed.inset-0').last()
        await clearDialog
            .getByTestId('label-selector')
            .getByRole('button')
            .nth(1)
            .click()
        await clearDialog
            .getByRole('button', { name: 'Save', exact: true })
            .click()
        await expect(clearDialog).toBeHidden()
        await expect(flowHeader.getByTestId('label-chip')).toHaveCount(0)
        await expect(flowHeader).toContainText('E2E Household')
        await flowActions.nth(1).click()

        const confirmation = page.locator('.fixed.inset-0').last()
        await confirmation
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        await expect(updatedHeading).toHaveCount(0)
        await expect(earningsTabCount).toHaveText(String(initialEarningsCount))
    })
})
