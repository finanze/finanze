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

    // Reload to ensure entity accounts are populated from the backend
    await page.reload()
    await page.waitForLoadState('networkidle')
}

/**
 * Helper: connect Trade Republic (2FA entity), entering the PIN code.
 * After connecting, reloads the page so entity accounts are populated.
 */
async function connectTradeRepublicAndReload(
    page: import('@playwright/test').Page,
) {
    await page.getByText('Trade Republic').first().click()
    await page.getByText('Enter credentials for').waitFor({ timeout: 5_000 })
    await page.locator('#phone').fill('+34612345678')
    await page.locator('#password').fill('1234')
    await page.getByRole('button', { name: 'Submit' }).click()

    await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
        timeout: 10_000,
    })
    for (const digit of MOCK_PIN_CODE) {
        await page.getByRole('button', { name: digit, exact: true }).click()
    }
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(
        page.getByText('Successfully logged in to Trade Republic'),
    ).toBeVisible({ timeout: 15_000 })

    // Reload to ensure entity accounts are populated from the backend
    await page.reload()
    await page.waitForLoadState('networkidle')
}

test.describe('Fetch Entity Data - Simple (Urbanitae)', () => {
    test('fetch data from connected entity via Integrations page', async ({
        authenticatedPage: page,
    }) => {
        // Navigate to entities
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Dismiss any PIN pad overlay from previous test
        const pinCancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (
            await pinCancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)
        ) {
            await pinCancelBtn.click()
            await page.waitForTimeout(500)
        }

        // Check if Urbanitae has a "Fetch" button (meaning it's connected)
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

            // Navigate back to Integrations
            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 15_000 })
        }

        // Click "Fetch" specifically on the Urbanitae card
        const urbanitaeFetch = page
            .locator('h3', { hasText: 'Urbanitae' })
            .first()
            .locator('../..')
            .getByRole('button', { name: 'Fetch' })
        await urbanitaeFetch.click()

        // Feature selector should appear
        await expect(
            page.getByText('Select features to fetch from Urbanitae'),
        ).toBeVisible({ timeout: 5_000 })

        // Click "Fetch data" to start scraping
        await page.getByRole('button', { name: 'Fetch data' }).click()

        // Wait for success toast
        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })
    })

    test('fetch data from connected entity via Dashboard refresh dropdown', async ({
        authenticatedPage: page,
    }) => {
        // Go to Integrations to check Urbanitae connection status
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Dismiss any PIN pad overlay from previous test
        const pinCancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (
            await pinCancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)
        ) {
            await pinCancelBtn.click()
            await page.waitForTimeout(500)
        }

        // Check if Urbanitae has a "Fetch" button (meaning it's connected)
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

        // Navigate to Summary/Dashboard page
        await page.getByRole('button', { name: 'Summary' }).click()
        await page
            .getByRole('heading', { name: 'Summary' })
            .waitFor({ timeout: 10_000 })

        // Open the Data refresh dropdown
        await page.getByRole('button', { name: 'Data' }).click()

        // Click the refresh button for Urbanitae
        await page
            .locator('button[aria-label="Refresh Urbanitae"]')
            .waitFor({ timeout: 5_000 })
        await page.locator('button[aria-label="Refresh Urbanitae"]').click()

        // Wait for success toast
        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })
    })
})

test.describe('Fetch Entity Data - 2FA (Trade Republic)', () => {
    test('fetch data from 2FA entity shows PIN pad', async ({
        authenticatedPage: page,
    }) => {
        // Navigate to Integrations
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Dismiss any PIN pad overlay from previous test
        const cancelBtn = page.getByRole('button', { name: 'Cancel' })
        if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
            await cancelBtn.click()
            await page.waitForTimeout(500)
        }

        // Check if Trade Republic has a "Fetch" button (meaning it's connected)
        const trCard = page
            .locator('h3', { hasText: 'Trade Republic' })
            .first()
            .locator('../..')
        const trFetchBtn = trCard.getByRole('button', { name: 'Fetch' })
        const trIsConnected = await trFetchBtn
            .isVisible({ timeout: 2_000 })
            .catch(() => false)

        if (!trIsConnected) {
            await connectTradeRepublicAndReload(page)

            // Navigate back to Integrations
            await page.getByRole('button', { name: 'Integrations' }).click()
            await page
                .getByRole('heading', { name: 'Integrations' })
                .waitFor({ timeout: 15_000 })
        }

        // Click "Fetch" specifically on the Trade Republic card
        const trFetch = page
            .locator('h3', { hasText: 'Trade Republic' })
            .first()
            .locator('../..')
            .getByRole('button', { name: 'Fetch' })
        await trFetch.click()

        // Feature selector should appear
        await expect(
            page.getByText('Select features to fetch from Trade Republic'),
        ).toBeVisible({ timeout: 5_000 })

        // Click "Fetch data" to start scraping
        await page.getByRole('button', { name: 'Fetch data' }).click()

        // Mock returns CODE_REQUESTED -> PIN pad should appear
        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        // Enter correct PIN
        for (const digit of MOCK_PIN_CODE) {
            await page.getByRole('button', { name: digit, exact: true }).click()
        }
        await page.getByRole('button', { name: 'Submit' }).click()

        // Wait for success toast
        await expect(
            page.getByText('Data successfully fetched from Trade Republic'),
        ).toBeVisible({ timeout: 30_000 })
    })
})
