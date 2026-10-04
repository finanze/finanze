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
    test('creates, edits, and deletes a recurring earning', async ({
        authenticatedPage: page,
    }) => {
        await page.setViewportSize({ width: 1440, height: 1000 })
        await navigateToMyMoneyPage(page, 'Recurring')
        await expect(
            page.getByRole('heading', { name: /^Recurring/ }),
        ).toBeVisible()
        await page.getByRole('tab', { name: /Earnings/ }).click()

        const earningsHeading = page.getByRole('heading', {
            name: 'Earnings',
            exact: true,
        })
        await earningsHeading.locator('../..').getByRole('button').click()

        const flowDialog = page.locator('.fixed.inset-0').last()
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
        await editDialog
            .getByRole('button', { name: 'Save', exact: true })
            .click()
        await expect(editDialog).toBeHidden()
        await expect(createdHeading).toHaveCount(0)

        const updatedHeading = page.getByRole('heading', {
            name: updatedFlowName,
            exact: true,
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
    })
})
