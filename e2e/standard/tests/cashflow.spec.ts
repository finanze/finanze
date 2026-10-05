import { expect, type Page } from '@playwright/test'
import { test } from '../fixtures/auth'
import { ensureEditMode } from '../helpers/edit-mode'
import { selectEntity } from '../helpers/entity-selector'
import { navigateToMyMoneyPage } from '../helpers/my-money'

const createdConnections = new WeakSet<Page>()

function alphabeticRunId(value: number): string {
    let result = ''
    while (value > 0) {
        result = String.fromCharCode(97 + (value % 26)) + result
        value = Math.floor(value / 26)
    }
    return result
}

const RECURRING_RUN_ID = alphabeticRunId(Date.now())
const SHARED_RECURRING_PAYEE = `E2E Cashflow Payee Cedar ${RECURRING_RUN_ID}`

const RECURRING_PAYEES = [
    `E2E Cashflow Track Alpha ${RECURRING_RUN_ID}`,
    `E2E Cashflow Ignore Bravo ${RECURRING_RUN_ID}`,
    SHARED_RECURRING_PAYEE,
    SHARED_RECURRING_PAYEE,
    `E2E Cashflow Payee Elm ${RECURRING_RUN_ID}`,
    `E2E Cashflow Payee Fern ${RECURRING_RUN_ID}`,
    `E2E Cashflow Payee Grove ${RECURRING_RUN_ID}`,
    `E2E Cashflow Payee Harbor ${RECURRING_RUN_ID}`,
    `E2E Cashflow Payee Indigo ${RECURRING_RUN_ID}`,
    `E2E Cashflow Payee Juniper ${RECURRING_RUN_ID}`,
    `E2E Cashflow Payee Kestrel ${RECURRING_RUN_ID}`,
] as const

async function navigateToCashflow(page: Page) {
    await navigateToMyMoneyPage(page, 'Activity')
    await expect(
        page.getByRole('heading', { name: 'Activity', exact: true }),
    ).toBeVisible()
}

async function navigateToTransactions(page: Page) {
    await page
        .getByRole('navigation')
        .getByRole('button', { name: 'Transactions', exact: true })
        .click()
    await expect(
        page.getByRole('heading', { name: 'Transactions' }).first(),
    ).toBeVisible({ timeout: 10_000 })
}

async function connectUrbanitaeIfNeeded(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await expect(
        page.getByRole('heading', { name: 'Integrations' }).first(),
    ).toBeVisible({ timeout: 15_000 })

    const entityCard = page
        .locator('h3', { hasText: 'Urbanitae' })
        .first()
        .locator('../..')
    const fetchButton = entityCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchButton
        .isVisible({ timeout: 3_000 })
        .catch(() => false)

    if (!isConnected) {
        await page.getByText('Urbanitae').first().click()
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 10_000 })
        await page.locator('#user').fill('test@example.com')
        await page.locator('#password').fill('MockPassword123')
        await page.getByRole('button', { name: 'Submit' }).click()
        await expect(
            page.getByText('Successfully logged in to Urbanitae'),
        ).toBeVisible({ timeout: 15_000 })
        createdConnections.add(page)

        await page.getByRole('button', { name: 'Integrations' }).click()
        await expect(
            page.getByRole('heading', { name: 'Integrations' }).first(),
        ).toBeVisible({ timeout: 15_000 })
    }

    const cancelButton = page.getByRole('button', {
        name: 'Cancel',
        exact: true,
    })
    if (await cancelButton.isVisible().catch(() => false)) {
        await cancelButton.click()
    }
}

function daysAgo(days: number): Date {
    const date = new Date()
    date.setHours(12, 0, 0, 0)
    date.setDate(date.getDate() - days)
    return date
}

function previousMonthDate(): Date {
    const today = new Date()
    return new Date(today.getFullYear(), today.getMonth() - 1, 15, 12, 0, 0)
}

function recurringAmount(index: number): string {
    if (index === 0) return '317.29'
    if (index === 3) return '240.00'
    return `${100 + index * 10}.00`
}

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

async function selectDate(page: Page, date: Date, fieldLabel = 'Date') {
    const dialog = page.locator('.fixed.inset-0').last()
    const dateField = dialog
        .getByText(fieldLabel, { exact: true })
        .locator('..')
    await dateField.getByRole('button').first().click()

    const calendar = page.locator('[data-radix-popper-content-wrapper]').last()
    await expect(calendar).toBeVisible()

    const targetMonth = new Intl.DateTimeFormat('en-US', {
        month: 'long',
        year: 'numeric',
    }).format(date)

    for (let attempt = 0; attempt < 24; attempt += 1) {
        const monthCaption = calendar.getByText(/^[A-Za-z]+ \d{4}$/)
        const visibleMonth = (await monthCaption.innerText()).trim()
        if (visibleMonth === targetMonth) break

        const visibleDate = new Date(`${visibleMonth} 1`)
        const targetDate = new Date(`${targetMonth} 1`)
        const direction =
            visibleDate > targetDate ? /previous month/i : /next month/i
        await calendar.getByRole('button', { name: direction }).click()
    }

    await expect(calendar.getByText(targetMonth, { exact: true })).toBeVisible()

    const monthName = new Intl.DateTimeFormat('en-US', {
        month: 'long',
    }).format(date)
    const dayName = new RegExp(
        `${monthName}\\s+${ordinal(date.getDate())},\\s+${date.getFullYear()}`,
    )
    const dayCell = calendar.getByRole('gridcell', { name: dayName })
    await expect(dayCell).toBeVisible()
    await dayCell.getByRole('button').click()
}

async function createManualTransaction(
    page: Page,
    name: string,
    amount: string,
    date: Date,
    transactionType: 'Inflow' | 'Outflow',
) {
    await page.getByRole('button', { name: 'Add', exact: true }).click()
    const dialog = page.locator('.fixed.inset-0').last()
    await expect(
        dialog.getByText('Add transaction', { exact: true }),
    ).toBeVisible({
        timeout: 5_000,
    })

    await selectEntity(page, 'Urbanitae', { inDialog: true })
    await dialog.locator('#transaction-name').fill(name)

    await dialog.locator('#transaction-product').click()
    await page.getByRole('option', { name: 'Account', exact: true }).click()
    await dialog.locator('#transaction-type').click()
    await page
        .getByRole('option', { name: transactionType, exact: true })
        .click()
    const iban = dialog.locator('input[id$="-iban"]')
    const counterparty = dialog.locator('input[id$="-counterparty"]')
    const retentions = dialog.locator('input[id$="-retentions"]')
    await expect(iban).toBeVisible()
    await expect(counterparty).toHaveCount(0)
    await expect(retentions).toHaveCount(0)
    const moreDetails = dialog.getByRole('button', {
        name: 'More details',
        exact: true,
    })
    await moreDetails.click()
    await expect(counterparty).toBeVisible()
    await expect(iban).toBeVisible()
    await expect(retentions).toHaveCount(0)
    await moreDetails.click()
    await expect(counterparty).toHaveCount(0)
    await dialog.locator('#transaction-amount').fill(amount)
    await dialog.locator('#transaction-currency').selectOption('EUR')
    await selectDate(page, date)

    await dialog.getByRole('button', { name: 'Save', exact: true }).click()
    await expect(
        dialog.getByText('Add transaction', { exact: true }),
    ).toBeHidden({ timeout: 10_000 })
}

async function readCashflowKpi(page: Page, testId: string): Promise<string> {
    return (
        await page
            .getByTestId(testId)
            .locator(':scope > div')
            .nth(1)
            .innerText()
    ).trim()
}

function parseCashflowAmount(text: string): number {
    const digits = text.replace(/\D/g, '')
    const amount = Number(digits) / 100
    return /[-\u2212]/.test(text) ? -amount : amount
}

async function readCashflowKpiAmount(
    page: Page,
    testId: string,
): Promise<number> {
    return parseCashflowAmount(await readCashflowKpi(page, testId))
}

async function selectCashflowPreset(
    page: Page,
    preset: 'thisMonth' | 'lastMonth' | 'last3Months',
) {
    const summaryResponse = page.waitForResponse((response) => {
        const url = new URL(response.url())
        return (
            url.pathname.endsWith('/cashflow') &&
            response.request().method() === 'GET'
        )
    })
    await page.getByTestId(`cashflow-preset-${preset}`).click()
    const summary = await (await summaryResponse).json()
    for (const metric of ['income', 'expenses', 'net'] as const) {
        await expect
            .poll(() => readCashflowKpiAmount(page, `kpi-${metric}`))
            .toBeCloseTo(summary.totals[metric], 2)
    }
}

async function expectNoHorizontalOverflow(page: Page) {
    const { pageWidth, viewportWidth } = await page.evaluate(() => ({
        pageWidth: Math.max(
            document.documentElement.scrollWidth,
            document.body.scrollWidth,
        ),
        viewportWidth: window.innerWidth,
    }))
    expect(pageWidth).toBeLessThanOrEqual(viewportWidth)
}

async function expectActionInTitleRow(page: Page, name: string) {
    const title = page.getByRole('heading', { name: 'Activity', exact: true })
    const action = page.getByRole('button', { name, exact: true })
    await expect(action).toBeVisible()

    const titleBounds = await title.boundingBox()
    const actionBounds = await action.boundingBox()
    expect(titleBounds).not.toBeNull()
    expect(actionBounds).not.toBeNull()
    if (!titleBounds || !actionBounds) {
        throw new Error(`${name} or the Activity title has no visible bounds`)
    }

    const titleCenter = titleBounds.y + titleBounds.height / 2
    const actionCenter = actionBounds.y + actionBounds.height / 2
    expect(Math.abs(titleCenter - actionCenter)).toBeLessThan(12)
    expect(actionBounds.x).toBeGreaterThan(titleBounds.x + titleBounds.width)
}

test.describe('Cashflow', () => {
    test.afterEach(async ({ authenticatedPage: page }) => {
        if (!createdConnections.delete(page)) return

        await page.setViewportSize({ width: 1440, height: 1000 })
        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Integrations', exact: true })
            .click()
        const entityCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        await entityCard
            .locator('button.text-red-600, button.text-red-500')
            .click()
        await page
            .getByRole('button', { name: 'Disconnect', exact: true })
            .click()
        await expect(
            entityCard.getByRole('button', { name: 'Fetch' }),
        ).toHaveCount(0)
    })

    test('toggles My Money without desktop navigation and keeps the mobile landing page', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        const navigation = page.getByRole('navigation')
        const myMoney = navigation.getByRole('button', {
            name: 'My Money',
            exact: true,
        })
        const recurring = navigation.getByRole('button', {
            name: 'Recurring',
            exact: true,
        })
        if ((await myMoney.getAttribute('aria-expanded')) === 'true') {
            await myMoney.click()
        }
        const initialUrl = page.url()
        await myMoney.click()
        await expect(myMoney).toHaveAttribute('aria-expanded', 'true')
        await expect(recurring).toBeVisible()
        await expect(page).toHaveURL(initialUrl)
        await recurring.click()
        await expect(page).toHaveURL(/\/management\/recurring$/)

        const recurringUrl = page.url()
        await myMoney.click()
        await expect(myMoney).toHaveAttribute('aria-expanded', 'false')
        await expect(recurring).toBeHidden()
        await expect(page).toHaveURL(recurringUrl)
        await myMoney.click()
        await expect(recurring).toBeVisible()
        await expect(page).toHaveURL(recurringUrl)

        await page.setViewportSize({ width: 390, height: 844 })
        await page
            .getByRole('button', { name: 'My Money', exact: true })
            .click()
        await expect(page).toHaveURL(/\/management$/)
        await expect(
            page.getByRole('heading', { name: 'My Money', exact: true }),
        ).toBeVisible()

        await page.setViewportSize({ width: 768, height: 844 })
        await expect(page).toHaveURL(/\/management\/cashflow$/)
        await expect(
            page.getByRole('heading', { name: 'My Money', exact: true }),
        ).toHaveCount(0)
        await expect(
            page.getByRole('heading', { name: 'Activity', exact: true }),
        ).toBeVisible()
        await expect(
            page.getByRole('button', { name: 'Back', exact: true }),
        ).toBeHidden()
    })

    test('shows the desktop New label action in the title row and opens its dialog', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToCashflow(page)
        await page.getByRole('tab', { name: /Labels/ }).click()

        await expectActionInTitleRow(page, 'New label')
        await page
            .getByRole('button', { name: 'New label', exact: true })
            .click()
        await expect(page.getByTestId('label-dialog')).toBeVisible()
        await expect(page.locator('#label-name')).toBeVisible()
    })

    test('shows the desktop New rule action in the title row and opens its dialog', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToCashflow(page)
        await page.getByRole('tab', { name: /Rules/ }).click()

        await expectActionInTitleRow(page, 'New rule')
        await page
            .getByRole('button', { name: 'New rule', exact: true })
            .click()
        await expect(page.getByTestId('rule-dialog')).toBeVisible()
        await expect(
            page.getByRole('heading', { name: 'New rule', exact: true }),
        ).toBeVisible()
        await expect(
            page.getByTestId('rule-dialog').getByRole('radio', {
                name: 'All',
                exact: true,
            }),
        ).toHaveAttribute('aria-checked', 'true')
    })

    test('creates a label and applies a matching rule to an existing outflow', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await ensureEditMode(page, 'DRAFT')
        await connectUrbanitaeIfNeeded(page)
        await navigateToTransactions(page)

        const transactionName = 'E2E Cashflow Rule Workflow Outflow'
        const labelName = 'E2E Cashflow Rule Workflow Label'
        const ruleName = 'E2E Cashflow Rule Workflow Rule'
        const amount = '47.13'
        await createManualTransaction(
            page,
            transactionName,
            amount,
            daysAgo(1),
            'Outflow',
        )

        await navigateToCashflow(page)
        await page.getByRole('tab', { name: /Labels/ }).click()
        await page
            .getByRole('button', { name: 'New label', exact: true })
            .click()
        const labelDialog = page.getByTestId('label-dialog')
        await labelDialog.locator('#label-name').fill(labelName)
        await labelDialog
            .getByRole('button', { name: 'Save', exact: true })
            .click()
        await expect(labelDialog).toBeHidden()

        await page.getByRole('tab', { name: /Rules/ }).click()
        await page
            .getByRole('button', { name: 'New rule', exact: true })
            .click()
        const ruleDialog = page.getByTestId('rule-dialog')
        await ruleDialog.locator('#rule-name').fill(ruleName)
        await ruleDialog.getByTestId('rule-text-value').fill(transactionName)
        await ruleDialog
            .getByTestId('label-selector')
            .getByRole('button', { name: labelName, exact: true })
            .click()
        await ruleDialog
            .getByRole('button', { name: 'Preview', exact: true })
            .click()
        const preview = ruleDialog.getByTestId('rule-preview')
        await expect(preview).toContainText(transactionName)
        await expect(preview).toContainText(/47[.,]13/)
        await ruleDialog
            .getByRole('button', { name: 'Save', exact: true })
            .click()
        await expect(ruleDialog).toBeHidden()

        await navigateToTransactions(page)
        await expect(
            page.getByText(transactionName, { exact: true }).first(),
        ).toBeVisible()
        await expect(
            page
                .locator('[data-testid="tx-labels"]:visible')
                .filter({ hasText: labelName })
                .first(),
        ).toBeVisible()

        await navigateToCashflow(page)
        const breakdownRow = page
            .getByTestId('cashflow-label-row')
            .filter({ hasText: labelName })
        await expect(breakdownRow).toBeVisible()
        await expect(breakdownRow).toContainText(/47[.,]13/)

        await page.getByRole('tab', { name: /Rules/ }).click()
        const ruleCard = page
            .getByTestId('rule-card')
            .filter({ hasText: ruleName })
        await expect(ruleCard).toBeVisible()
        await ruleCard
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        let confirmation = page.locator('.fixed.inset-0').last()
        await confirmation
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        await expect(ruleCard).toHaveCount(0)

        await page.getByRole('tab', { name: /Labels/ }).click()
        const labelCard = page
            .locator('[data-testid^="label-card-"]')
            .filter({ hasText: labelName })
        await expect(labelCard).toBeVisible()
        await labelCard
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        confirmation = page.locator('.fixed.inset-0').last()
        await confirmation
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        await expect(labelCard).toHaveCount(0)
    })

    test('summarizes account inflows and outflows in their selected periods', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await ensureEditMode(page, 'DRAFT')
        await connectUrbanitaeIfNeeded(page)
        const entityCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        await entityCard.getByRole('button', { name: 'Fetch' }).click()
        const fetchTitle = page.getByText(
            'Select features to fetch from Urbanitae',
        )
        await expect(fetchTitle).toBeVisible()
        await page
            .locator('.fixed.inset-0')
            .last()
            .getByRole('button', { name: 'Fetch', exact: true })
            .click()
        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible()
        await expect(fetchTitle).toBeHidden()
        await navigateToCashflow(page)
        await expect(page.getByTestId('cashflow-kpis')).toBeVisible()

        await selectCashflowPreset(page, 'thisMonth')
        const incomeBeforeThisMonth = await readCashflowKpiAmount(
            page,
            'kpi-income',
        )
        const expensesBeforeThisMonth = await readCashflowKpiAmount(
            page,
            'kpi-expenses',
        )
        const netBeforeThisMonth = await readCashflowKpiAmount(page, 'kpi-net')

        await selectCashflowPreset(page, 'last3Months')
        const incomeBeforeLast3Months = await readCashflowKpiAmount(
            page,
            'kpi-income',
        )
        const expensesBeforeLast3Months = await readCashflowKpiAmount(
            page,
            'kpi-expenses',
        )
        const netBeforeLast3Months = await readCashflowKpiAmount(
            page,
            'kpi-net',
        )

        await selectCashflowPreset(page, 'lastMonth')
        const incomeBeforeLastMonth = await readCashflowKpiAmount(
            page,
            'kpi-income',
        )
        const expensesBeforeLastMonth = await readCashflowKpiAmount(
            page,
            'kpi-expenses',
        )
        const netBeforeLastMonth = await readCashflowKpiAmount(page, 'kpi-net')

        await navigateToTransactions(page)
        await createManualTransaction(
            page,
            'E2E Cashflow Period Current Inflow',
            '300.00',
            daysAgo(0),
            'Inflow',
        )
        await createManualTransaction(
            page,
            'E2E Cashflow Period Previous Month Outflow',
            '125.43',
            previousMonthDate(),
            'Outflow',
        )

        await navigateToCashflow(page)
        await expect(page.getByTestId('cashflow-kpis')).toBeVisible()
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-income'))
            .toBeCloseTo(incomeBeforeLast3Months + 300, 2)
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-expenses'))
            .toBeCloseTo(expensesBeforeLast3Months + 125.43, 2)
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-net'))
            .toBeCloseTo(netBeforeLast3Months + 174.57, 2)

        await selectCashflowPreset(page, 'thisMonth')
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-income'))
            .toBeCloseTo(incomeBeforeThisMonth + 300, 2)
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-expenses'))
            .toBeCloseTo(expensesBeforeThisMonth, 2)
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-net'))
            .toBeCloseTo(netBeforeThisMonth + 300, 2)

        await selectCashflowPreset(page, 'lastMonth')
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-expenses'))
            .toBeCloseTo(expensesBeforeLastMonth + 125.43, 2)
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-net'))
            .toBeCloseTo(netBeforeLastMonth - 125.43, 2)
        await expect
            .poll(() => readCashflowKpiAmount(page, 'kpi-income'))
            .toBeCloseTo(incomeBeforeLastMonth, 2)
    })

    test('separates same-payee amounts, replenishes ignored rows, and restores all ignored', async ({
        authenticatedPage: page,
    }) => {
        test.setTimeout(180_000)
        await page.setViewportSize({ width: 1440, height: 1000 })
        await ensureEditMode(page, 'DRAFT')
        await connectUrbanitaeIfNeeded(page)
        await navigateToTransactions(page)

        for (const days of [61, 31, 1]) {
            for (const [index, name] of RECURRING_PAYEES.entries()) {
                const date = daysAgo(days + (index === 3 ? 15 : 0))
                await createManualTransaction(
                    page,
                    name,
                    recurringAmount(index),
                    date,
                    'Outflow',
                )
            }
        }

        await navigateToCashflow(page)
        const recurring = page.getByTestId('recurring-movements')
        const activeRows = recurring.getByTestId('recurring-movement')
        await expect(activeRows).toHaveCount(10, { timeout: 20_000 })

        const trackedPayee = RECURRING_PAYEES[RECURRING_PAYEES.length - 1]
        const trackRow = activeRows.filter({ hasText: trackedPayee })
        await expect(trackRow).toBeVisible()
        await trackRow
            .getByRole('button', { name: 'Track', exact: true })
            .click()
        await expect(trackRow.getByTestId('tracked-badge')).toBeVisible({
            timeout: 15_000,
        })
        await expect(trackRow.getByTestId('ignore-recurring')).toHaveCount(0)

        const showMoreRecurring = recurring.getByRole('button', {
            name: 'Show more',
        })
        await expect(showMoreRecurring).toBeVisible()
        const sharedRows = activeRows.filter({
            hasText: SHARED_RECURRING_PAYEE,
        })
        await expect(sharedRows).toHaveCount(2)
        const sharedRowTexts = await sharedRows.allInnerTexts()
        expect(sharedRowTexts.some((text) => text.includes('120'))).toBe(true)
        expect(sharedRowTexts.some((text) => text.includes('240'))).toBe(true)

        const collapsedRecurring = recurring
        const collapsedRows = activeRows
        const collapsedRowTexts = await collapsedRows.allInnerTexts()
        const expectedSeries = RECURRING_PAYEES.map((payee, index) => ({
            payee,
            amount: recurringAmount(index).split('.')[0],
        }))
        const omittedSeries = expectedSeries.find(
            ({ payee, amount }) =>
                !collapsedRowTexts.some(
                    (text) => text.includes(payee) && text.includes(amount),
                ),
        )
        if (!omittedSeries) {
            throw new Error(
                'The 10-row view omitted no seeded recurring series',
            )
        }

        await expect(page.getByTestId('cashflow-kpis')).toBeVisible()
        const cashflowKpis = page.getByTestId('cashflow-kpis')
        const totalsBeforeIgnore = (await cashflowKpis.innerText())
            .replace(/\s+/g, ' ')
            .trim()
        const ignoredSharedRow = collapsedRows
            .filter({ hasText: SHARED_RECURRING_PAYEE })
            .filter({ hasText: '120' })
        await expect(ignoredSharedRow).toBeVisible()
        await ignoredSharedRow.getByTestId('ignore-recurring').click()
        await expect(collapsedRows).toHaveCount(10)
        await expect(
            collapsedRows
                .filter({ hasText: SHARED_RECURRING_PAYEE })
                .filter({ hasText: '240' }),
        ).toHaveCount(1)
        await expect(
            collapsedRows
                .filter({ hasText: omittedSeries.payee })
                .filter({ hasText: omittedSeries.amount }),
        ).toBeVisible()
        await expect(
            collapsedRecurring.getByTestId('ignored-recurring'),
        ).toContainText('Ignored (1)')
        await expect
            .poll(async () =>
                (await cashflowKpis.innerText()).replace(/\s+/g, ' ').trim(),
            )
            .toBe(totalsBeforeIgnore)

        await navigateToTransactions(page)
        await navigateToCashflow(page)
        const persistedRecurring = page.getByTestId('recurring-movements')
        const persistedRows =
            persistedRecurring.getByTestId('recurring-movement')
        await expect(persistedRows).toHaveCount(10, { timeout: 20_000 })
        const persistedIgnored =
            persistedRecurring.getByTestId('ignored-recurring')
        await expect(persistedIgnored).toContainText('Ignored (1)')
        const persistedIgnoredRows = persistedRecurring.getByTestId(
            'ignored-recurring-movement',
        )
        if (!(await persistedIgnoredRows.count())) {
            await persistedIgnored.locator(':scope > button').click()
        }

        const ignoredRow = persistedIgnoredRows
            .filter({ hasText: SHARED_RECURRING_PAYEE })
            .filter({ hasText: '120' })
        await expect(ignoredRow).toBeVisible()
        await ignoredRow.getByRole('button', { name: 'Restore' }).click()
        await expect(
            persistedRecurring.getByTestId('ignored-recurring'),
        ).toHaveCount(0)
        await expect(
            persistedRecurring
                .getByTestId('recurring-movement')
                .filter({ hasText: SHARED_RECURRING_PAYEE }),
        ).toHaveCount(2)

        await navigateToMyMoneyPage(page, 'Recurring')
        await page.getByRole('tab', { name: /Expenses/ }).click()
        const trackedFlowHeading = page.getByRole('heading', {
            name: trackedPayee,
            exact: true,
        })
        const trackedFlowHeader = page
            .locator('div[role="button"][aria-expanded]')
            .filter({ has: trackedFlowHeading })
        await expect(trackedFlowHeader).toBeVisible()
        if (
            (await trackedFlowHeader.getAttribute('aria-expanded')) !== 'true'
        ) {
            await trackedFlowHeader.click()
        }
        const trackedFlowActions = trackedFlowHeader
            .locator('..')
            .locator('[data-no-expand]')
            .getByRole('button')
        await expect(trackedFlowActions).toHaveCount(2)
        await trackedFlowActions.nth(1).click()
        const trackedFlowConfirmation = page.locator('.fixed.inset-0').last()
        await trackedFlowConfirmation
            .getByRole('button', { name: 'Delete', exact: true })
            .click()
        await expect(trackedFlowHeading).toHaveCount(0)

        await navigateToCashflow(page)
        const allRecurring = page.getByTestId('recurring-movements')
        const allActiveRows = allRecurring.getByTestId('recurring-movement')
        await expect(allActiveRows).toHaveCount(10, { timeout: 20_000 })
        const showMore = allRecurring.getByRole('button', { name: 'Show more' })
        await expect(showMore).toBeVisible()
        await showMore.click()
        await expect(allActiveRows).toHaveCount(RECURRING_PAYEES.length)
        const allSeriesCount = await allActiveRows.count()
        expect(allSeriesCount).toBeGreaterThan(10)
        while (await allActiveRows.count()) {
            const previousCount = await allActiveRows.count()
            const row = allActiveRows.first()
            await expect(row.getByTestId('ignore-recurring')).toBeVisible()
            await row.getByTestId('ignore-recurring').click()
            await expect(allActiveRows).toHaveCount(previousCount - 1)
        }

        const allIgnoredSection = allRecurring.getByTestId('ignored-recurring')
        await expect(allIgnoredSection).toContainText(
            `Ignored (${allSeriesCount})`,
        )
        const allIgnoredRows = allRecurring.getByTestId(
            'ignored-recurring-movement',
        )
        if (!(await allIgnoredRows.count())) {
            await allIgnoredSection.locator(':scope > button').click()
        }
        await expect(allIgnoredRows).toHaveCount(allSeriesCount)

        await page.setViewportSize({ width: 768, height: 844 })
        await navigateToMyMoneyPage(page, 'Recurring')
        await navigateToMyMoneyPage(page, 'Activity')
        await page.setViewportSize({ width: 390, height: 844 })
        const mobileRecurring = page.getByTestId('recurring-movements')
        const mobileIgnored = mobileRecurring.getByTestId('ignored-recurring')
        await expect(mobileIgnored).toContainText(`Ignored (${allSeriesCount})`)
        const mobileIgnoredRows = mobileRecurring.getByTestId(
            'ignored-recurring-movement',
        )
        if (!(await mobileIgnoredRows.count())) {
            await mobileIgnored.locator(':scope > button').click()
        }
        await expect(mobileIgnoredRows).toHaveCount(allSeriesCount)
        await expectNoHorizontalOverflow(page)

        await page.getByRole('tab', { name: /Labels/ }).click()
        const newLabelButton = page.getByRole('button', {
            name: 'New label',
            exact: true,
        })
        await expect(newLabelButton).toBeVisible()
        await newLabelButton.click()
        const mobileLabelDialog = page.getByTestId('label-dialog')
        await expect(mobileLabelDialog.locator('#label-name')).toBeVisible()
        await mobileLabelDialog
            .getByRole('button', { name: 'Cancel', exact: true })
            .click()
        await expect(mobileLabelDialog).toBeHidden()

        await page.getByRole('tab', { name: /Rules/ }).click()
        const newRuleButton = page.getByRole('button', {
            name: 'New rule',
            exact: true,
        })
        await expect(newRuleButton).toBeVisible()
        await newRuleButton.click()
        const mobileRuleDialog = page.getByTestId('rule-dialog')
        await expect(mobileRuleDialog).toBeVisible()
        await mobileRuleDialog
            .getByRole('button', { name: 'Cancel', exact: true })
            .click()
        await expect(mobileRuleDialog).toBeHidden()

        await page.getByRole('tab', { name: /Analysis/ }).click()
        const cleanupRecurring = page.getByTestId('recurring-movements')
        const cleanupIgnored = cleanupRecurring.getByTestId('ignored-recurring')
        const ignoredRowsToRestore = cleanupRecurring.getByTestId(
            'ignored-recurring-movement',
        )
        if (!(await ignoredRowsToRestore.count())) {
            await cleanupIgnored.locator(':scope > button').click()
        }
        while (await ignoredRowsToRestore.count()) {
            const previousCount = await ignoredRowsToRestore.count()
            await ignoredRowsToRestore
                .first()
                .getByRole('button', { name: 'Restore' })
                .click()
            await expect(ignoredRowsToRestore).toHaveCount(previousCount - 1)
        }
        await expect(
            cleanupRecurring.getByTestId('recurring-movement'),
        ).toHaveCount(Math.min(allSeriesCount, 10))
    })
})
