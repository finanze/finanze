import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const POLYMARKET_CREDENTIAL = 'mock-polymarket-user'

function marketForecastCard(page: Page) {
    return page
        .locator('div[class*="rounded"][class*="border"]', {
            has: page.locator('span:text-is("Polymarket")'),
        })
        .first()
}

async function goToIntegrations(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })
}

async function scrollToPolymarket(page: Page) {
    const polymarket = page.locator('span:text-is("Polymarket")').first()
    if (!(await polymarket.isVisible().catch(() => false))) {
        const otherCategory = page
            .getByRole('button', { name: 'Other', exact: true })
            .last()
        await otherCategory.scrollIntoViewIfNeeded()
        await otherCategory.click()
    }
    await polymarket.scrollIntoViewIfNeeded()
    await page.waitForTimeout(300)
}

async function connectPolymarketAccount(
    page: Page,
    accountName: string,
    clickEntity = true,
) {
    if (clickEntity) {
        await scrollToPolymarket(page)
        await marketForecastCard(page).click()
    }

    await page.getByText('Enter credentials for').waitFor({ timeout: 10_000 })
    await page.locator('#identifier').fill(POLYMARKET_CREDENTIAL)

    const addNameButton = page.getByText('Name this account')
    if (await addNameButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await addNameButton.click()
    }

    await page.locator('#accountName').fill(accountName)
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(
        page.getByText('Successfully logged in to Polymarket'),
    ).toBeVisible({ timeout: 15_000 })
}

test.describe('Market Forecast Multi-Account', () => {
    test('connects and disconnects individual Polymarket accounts', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)
        await scrollToPolymarket(page)
        await connectPolymarketAccount(page, 'Main')

        await goToIntegrations(page)
        await scrollToPolymarket(page)
        await expect(marketForecastCard(page).getByText('Main')).toBeVisible({
            timeout: 5_000,
        })

        await marketForecastCard(page)
            .locator('button')
            .filter({ has: page.locator('svg.lucide-plus') })
            .click()
        await connectPolymarketAccount(page, 'DCA', false)

        await goToIntegrations(page)
        await scrollToPolymarket(page)
        await marketForecastCard(page)
            .getByRole('button', { name: 'Manage' })
            .click()

        const dialog = page
            .locator('.fixed')
            .filter({ hasText: 'Manage Accounts' })
            .first()
        await expect(dialog.getByText('Main')).toBeVisible({ timeout: 5_000 })
        await expect(dialog.getByText('DCA')).toBeVisible({ timeout: 5_000 })
        await expect(dialog.getByText('Connected')).toHaveCount(2)

        const accountRows = dialog.locator('.rounded-lg.border.p-3')
        await accountRows
            .last()
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
        await expect(marketForecastCard(page).getByText('Main')).toBeVisible({
            timeout: 5_000,
        })
        await expect(marketForecastCard(page).getByText('DCA')).toHaveCount(0)
    })
})
