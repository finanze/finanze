import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { MOCK_PIN_CODE } from '../../helpers/constants'

/**
 * Helper: connect an entity from the Integrations page via login form.
 * Assumes the page is already on the Integrations page.
 * After connecting, reloads the page so entity accounts are populated.
 */
async function connectAndReload(
    page: import('@playwright/test').Page,
    entityName: string,
    credentials: Record<string, string>,
) {
    await page.getByText(entityName).first().click()
    await page.getByText('Enter credentials for').waitFor({ timeout: 5_000 })
    for (const [field, value] of Object.entries(credentials)) {
        await page.locator(`#${field}`).fill(value)
    }
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(
        page.getByText(`Successfully logged in to ${entityName}`),
    ).toBeVisible({ timeout: 15_000 })

    await page.reload()
    await page.waitForLoadState('networkidle')
}

/**
 * Helper: connect Wecity (2FA entity), entering the PIN code.
 * After connecting, reloads the page so entity accounts are populated.
 */
async function connectWecityAndReload(page: import('@playwright/test').Page) {
    await page.getByText('Wecity').first().click()
    await page.getByText('Enter credentials for').waitFor({ timeout: 5_000 })
    await page.locator('#user').fill('test@example.com')
    await page.locator('#password').fill('MockPassword123')
    await page.getByRole('button', { name: 'Submit' }).click()

    await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
        timeout: 10_000,
    })
    for (const digit of MOCK_PIN_CODE) {
        await page.getByRole('button', { name: digit, exact: true }).click()
    }
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(
        page.getByText('Successfully logged in to Wecity'),
    ).toBeVisible({ timeout: 15_000 })

    await page.reload()
    await page.waitForLoadState('networkidle')
}

test.describe('Fetch Entity Data - Simple (Urbanitae)', () => {
    test('fetch data from connected entity via Integrations page', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const pinCancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (
            await pinCancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)
        ) {
            await pinCancelBtn.click()
            await page.waitForTimeout(500)
        }

        const urbanitaeCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        const fetchBtn = urbanitaeCard.getByRole('button', { name: 'Fetch' })
        const urbanitaeIsConnected = await fetchBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!urbanitaeIsConnected) {
            await connectAndReload(page, 'Urbanitae', {
                user: 'test@example.com',
                password: 'MockPassword123',
            })

            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 15_000 })
        }

        const urbanitaeFetch = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
            .getByRole('button', { name: 'Fetch' })
        await urbanitaeFetch.click()

        await expect(
            page.getByText('Select features to fetch from Urbanitae'),
        ).toBeVisible({ timeout: 5_000 })

        await page.getByRole('button', { name: 'Fetch data' }).click()

        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })
    })

    test('fetch data from connected entity via Dashboard refresh dropdown', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const pinCancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (
            await pinCancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)
        ) {
            await pinCancelBtn.click()
            await page.waitForTimeout(500)
        }

        const urbanitaeCard = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
        const fetchBtn = urbanitaeCard.getByRole('button', { name: 'Fetch' })
        const urbanitaeIsConnected = await fetchBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!urbanitaeIsConnected) {
            await connectAndReload(page, 'Urbanitae', {
                user: 'test@example.com',
                password: 'MockPassword123',
            })
        }

        await page.getByRole('button', { name: 'Summary' }).click()
        await page
            .getByRole('heading', { name: 'Summary' })
            .waitFor({ timeout: 10_000 })

        await page.getByRole('button', { name: 'Data' }).click()

        await page
            .locator('button[aria-label="Refresh Urbanitae"]')
            .waitFor({ timeout: 5_000 })
        await page.locator('button[aria-label="Refresh Urbanitae"]').click()

        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })
    })
})

test.describe('Fetch Entity Data - 2FA (Wecity)', () => {
    test('fetch data from 2FA entity shows PIN pad', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const cancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await cancelBtn.click()
            await page.waitForTimeout(500)
        }

        const wecityCard = page
            .locator('h3', { hasText: 'Wecity' })
            .first()
            .locator('../..')
        const wecityFetchBtn = wecityCard.getByRole('button', {
            name: 'Fetch',
        })
        const wecityIsConnected = await wecityFetchBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!wecityIsConnected) {
            await connectWecityAndReload(page)

            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 15_000 })
        }

        const wecityFetch = page
            .locator('h3', { hasText: 'Wecity' })
            .first()
            .locator('../..')
            .getByRole('button', { name: 'Fetch' })
        await wecityFetch.click()

        await expect(
            page.getByText('Select features to fetch from Wecity'),
        ).toBeVisible({ timeout: 5_000 })

        await page.getByRole('button', { name: 'Fetch data' }).click()

        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        for (const digit of MOCK_PIN_CODE) {
            await page.getByRole('button', { name: digit, exact: true }).click()
        }
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(
            page.getByText('Data successfully fetched from Wecity'),
        ).toBeVisible({ timeout: 30_000 })
    })
})

test.describe('Fetch Entity Data - Manual Login (Trade Republic)', () => {
    test('manual login entity shows use app error', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const cancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await cancelBtn.click()
            await page.waitForTimeout(500)
        }

        await page.getByText('Trade Republic').first().click()

        await expect(
            page.getByText('Use the app in order to do manual log in.'),
        ).toBeVisible({ timeout: 10_000 })
    })
})
