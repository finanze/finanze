import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { MOCK_PIN_CODE, UNICAJA_CREDENTIALS } from '../../helpers/constants'
import { selectEntity } from '../../helpers/entity-selector'

function entityCard(page: Page, name: string) {
    return page
        .locator('h3')
        .filter({
            has: page.getByRole('img', { name, exact: true }),
        })
        .first()
        .locator('../..')
}

function unicajaCard(page: Page) {
    return entityCard(page, 'Unicaja')
}

async function goToIntegrations(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

    const cancelBtn = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await cancelBtn.click()
        await page.waitForTimeout(500)
    }
}

async function connectUnicajaIfNeeded(page: Page) {
    await goToIntegrations(page)

    const connected = await unicajaCard(page)
        .getByRole('button', { name: 'Fetch' })
        .isVisible({ timeout: 2_000 })
        .catch(() => false)
    if (connected) return

    await page.getByText('Unicaja').first().click()
    await page.getByText('Enter credentials for').waitFor({ timeout: 10_000 })
    await page.locator('#user').fill(UNICAJA_CREDENTIALS.user)
    await page.locator('#password').fill(UNICAJA_CREDENTIALS.password)
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(
        page.getByText('Successfully logged in to Unicaja'),
    ).toBeVisible({ timeout: 15_000 })

    await page.reload()
    await page.waitForLoadState('networkidle')
    await goToIntegrations(page)
}

async function fetchWithOlderTransactions(page: Page) {
    await unicajaCard(page).getByRole('button', { name: 'Fetch' }).click()
    await expect(
        page.getByText('Select features to fetch from Unicaja'),
    ).toBeVisible({ timeout: 5_000 })

    const modalFetch = page.locator('.fixed').getByRole('button', {
        name: 'Fetch',
    })
    await expect(modalFetch).toBeEnabled({ timeout: 5_000 })

    await expect(
        page.getByText('Include older account transactions'),
    ).toBeVisible()
    const toggle = page.locator('#two-factor-old-txs')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-checked', 'true')

    await modalFetch.click()

    await expect(page.getByText(/Enter 6-digit code for/)).toBeVisible({
        timeout: 30_000,
    })
    await expect(
        page.getByText('Select features to fetch from Unicaja'),
    ).toBeHidden()
    await expect(
        page.getByText(
            'Main data is already fetched. Enter the extra code sent to ******447 to also fetch older account transactions.',
        ),
    ).toBeVisible()
}

test.describe('Two-factor older account transactions (Unicaja)', () => {
    test('fetches older account transactions after entering the extra code', async ({
        authenticatedPage: page,
    }) => {
        await connectUnicajaIfNeeded(page)
        await fetchWithOlderTransactions(page)

        for (const digit of MOCK_PIN_CODE) {
            await page.getByRole('button', { name: digit, exact: true }).click()
        }
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(
            page.getByText('Data successfully fetched from Unicaja'),
        ).toBeVisible({ timeout: 30_000 })

        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await selectEntity(page, 'Unicaja')
        await page.keyboard.press('Escape')
        await page.getByRole('button', { name: 'Search', exact: true }).click()
        await expect(page.getByText('Mock Old Account Tx').first()).toBeVisible(
            { timeout: 10_000 },
        )
    })

    test('cancelling the extra code skips older account transactions', async ({
        authenticatedPage: page,
    }) => {
        await connectUnicajaIfNeeded(page)
        await fetchWithOlderTransactions(page)

        await page.getByRole('button', { name: 'Cancel' }).click()
        await expect(
            page.getByText(
                'Main data is already saved. Do you want to skip older account transactions?',
            ),
        ).toBeVisible()
        await page.getByRole('button', { name: 'Confirm' }).click()

        await expect(
            page.getByText(
                'Older account transactions from Unicaja were skipped',
            ),
        ).toBeVisible({ timeout: 5_000 })
    })

    test('toggle is hidden when transactions are not selected', async ({
        authenticatedPage: page,
    }) => {
        await connectUnicajaIfNeeded(page)

        await unicajaCard(page).getByRole('button', { name: 'Fetch' }).click()
        await expect(
            page.getByText('Select features to fetch from Unicaja'),
        ).toBeVisible({ timeout: 5_000 })
        await expect(page.locator('#two-factor-old-txs')).toBeVisible()

        await page
            .locator('.fixed')
            .getByText('Transactions', { exact: true })
            .click()

        await expect(page.locator('#two-factor-old-txs')).toBeHidden()
    })
})

async function connectIngIfNeeded(page: Page) {
    await goToIntegrations(page)

    const connected = await entityCard(page, 'ING')
        .getByRole('button', { name: 'Fetch' })
        .isVisible({ timeout: 2_000 })
        .catch(() => false)
    if (connected) return

    await page
        .locator('h3')
        .filter({ has: page.getByRole('img', { name: 'ING', exact: true }) })
        .click()
    await expect(page.getByText('Successfully logged in to ING')).toBeVisible({
        timeout: 15_000,
    })

    await page.reload()
    await page.waitForLoadState('networkidle')
    await goToIntegrations(page)
}

async function fetchIngWithOlderTransactions(page: Page) {
    await entityCard(page, 'ING').getByRole('button', { name: 'Fetch' }).click()
    await expect(
        page.getByText('Select features to fetch from ING'),
    ).toBeVisible({ timeout: 5_000 })

    const modalFetch = page.locator('.fixed').getByRole('button', {
        name: 'Fetch',
    })
    await expect(modalFetch).toBeEnabled({ timeout: 5_000 })

    const toggle = page.locator('#two-factor-old-txs')
    await toggle.click()
    await expect(toggle).toHaveAttribute('aria-checked', 'true')

    await modalFetch.click()

    await expect(
        page.getByText(
            'Open the financial institution app on your phone and confirm the request to access older transactions.',
        ),
    ).toBeVisible({ timeout: 30_000 })
}

test.describe('Two-factor older account transactions (ING in-app)', () => {
    test('fetches older account transactions after in-app approval', async ({
        authenticatedPage: page,
    }) => {
        await connectIngIfNeeded(page)
        await fetchIngWithOlderTransactions(page)

        await expect(
            page.getByText('Data successfully fetched from ING'),
        ).toBeVisible({ timeout: 30_000 })
        await expect(
            page.getByText(
                'Open the financial institution app on your phone and confirm the request to access older transactions.',
            ),
        ).toBeHidden()

        await page
            .getByRole('navigation')
            .getByRole('button', { name: 'Transactions' })
            .click()
        await page
            .getByRole('heading', { name: 'Transactions' })
            .first()
            .waitFor({ timeout: 10_000 })
        await selectEntity(page, 'ING')
        await page.keyboard.press('Escape')
        await page.getByRole('button', { name: 'Search', exact: true }).click()
        await expect(page.getByText('Mock Old Account Tx').first()).toBeVisible(
            { timeout: 10_000 },
        )
    })

    test('cancelling the in-app approval skips older account transactions', async ({
        authenticatedPage: page,
    }) => {
        await connectIngIfNeeded(page)
        await fetchIngWithOlderTransactions(page)

        await page
            .locator('.fixed')
            .getByRole('button', { name: 'Cancel' })
            .click()

        await expect(
            page.getByText('Older account transactions from ING were skipped'),
        ).toBeVisible({ timeout: 10_000 })
    })
})
