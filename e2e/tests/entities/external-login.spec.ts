import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import {
    TRADE_REPUBLIC_CREDENTIALS,
    UNICAJA_CREDENTIALS,
} from '../../helpers/constants'

/**
 * Helper: navigate to Integrations and dismiss any pending PIN/cancel overlay.
 */
async function goToIntegrations(page: import('@playwright/test').Page) {
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

/**
 * Helper: check if an entity is connected (has a Fetch button visible).
 */
async function isEntityConnected(
    page: import('@playwright/test').Page,
    entityName: string,
): Promise<boolean> {
    const card = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    return await card
        .getByRole('button', { name: 'Fetch' })
        .isVisible({ timeout: 2_000 })
        .catch(() => false)
}

/**
 * Helper: click Fetch on an entity card, select all features, and click "Fetch data".
 */
async function fetchEntity(
    page: import('@playwright/test').Page,
    entityName: string,
) {
    const card = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    await card.getByRole('button', { name: 'Fetch' }).click()

    await expect(
        page.getByText(`Select features to fetch from ${entityName}`),
    ).toBeVisible({ timeout: 5_000 })

    await page.getByRole('button', { name: 'Fetch data' }).click()
}

test.describe('External Login - Trade Republic (partial creds + form)', () => {
    test('connect via external login then fetch with MANUAL_LOGIN flow', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)

        if (!(await isEntityConnected(page, 'Trade Republic'))) {
            // Click Trade Republic — triggers external login mock
            await page.getByText('Trade Republic').first().click()

            // Mock fires completion with { awsWafToken } only.
            // Visible creds (phone, password) are missing → login form appears.
            await page
                .getByText('Enter credentials for')
                .waitFor({ timeout: 10_000 })

            await page.locator('#phone').fill(TRADE_REPUBLIC_CREDENTIALS.phone)
            await page
                .locator('#password')
                .fill(TRADE_REPUBLIC_CREDENTIALS.password)
            await page.getByRole('button', { name: 'Submit' }).click()

            await expect(
                page.getByText('Successfully logged in to Trade Republic'),
            ).toBeVisible({ timeout: 15_000 })

            await page.reload()
            await page.waitForLoadState('networkidle')
            await goToIntegrations(page)
        }

        // Fetch — backend has session → returns MANUAL_LOGIN → mock auto-completes
        // with flow: "fetch" → scrape proceeds directly
        await fetchEntity(page, 'Trade Republic')

        await expect(
            page.getByText('Data successfully fetched from Trade Republic'),
        ).toBeVisible({ timeout: 30_000 })
    })
})

test.describe('External Login - ING (full creds from external login)', () => {
    test('connect via external login (no form) then fetch', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)

        if (!(await isEntityConnected(page, 'ING'))) {
            // Click ING — triggers external login mock
            // Use h3 locator to avoid matching sidebar "Banking" text
            await page.locator('h3', { hasText: 'ING' }).first().click()

            // Mock fires completion with all 5 INTERNAL_TEMP creds.
            // Zero visible creds → login() called directly, no form shown.
            await expect(
                page.getByText('Successfully logged in to ING'),
            ).toBeVisible({ timeout: 15_000 })

            await page.reload()
            await page.waitForLoadState('networkidle')
            await goToIntegrations(page)
        }

        // Fetch — backend has session → MANUAL_LOGIN → mock auto-completes → scrape
        await fetchEntity(page, 'ING')

        await expect(
            page.getByText('Data successfully fetched from ING'),
        ).toBeVisible({ timeout: 30_000 })
    })
})

test.describe('External Login - Unicaja (cookie + visible form)', () => {
    test('connect via external login with form then fetch', async ({
        authenticatedPage: page,
    }) => {
        await goToIntegrations(page)

        if (!(await isEntityConnected(page, 'Unicaja'))) {
            // Click Unicaja — triggers external login mock
            await page.getByText('Unicaja').first().click()

            // Mock fires completion with { abck } only.
            // Visible creds (user, password) are missing → login form appears.
            await page
                .getByText('Enter credentials for')
                .waitFor({ timeout: 10_000 })

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

        // Fetch — backend has session → MANUAL_LOGIN → mock auto-completes → scrape
        await fetchEntity(page, 'Unicaja')

        await expect(
            page.getByText('Data successfully fetched from Unicaja'),
        ).toBeVisible({ timeout: 30_000 })
    })
})
