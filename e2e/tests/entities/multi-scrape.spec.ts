import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { MOCK_PIN_CODE } from '../../helpers/constants'

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

async function connectEntityIfNeeded(
    page: Page,
    entityName: string,
    credentials: Record<string, string>,
) {
    await goToIntegrations(page)

    const entityCard = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchBtn = entityCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchBtn
        .isVisible({ timeout: 2_000 })
        .catch(() => false)

    if (!isConnected) {
        await page.getByText(entityName).first().click()
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 10_000 })
        for (const [field, value] of Object.entries(credentials)) {
            await page.locator(`#${field}`).fill(value)
        }
        await page.getByRole('button', { name: 'Submit' }).click()
        await expect(
            page.getByText(`Successfully logged in to ${entityName}`),
        ).toBeVisible({ timeout: 20_000 })

        await page.reload()
        await page.waitForLoadState('networkidle')
    }
}

async function connectPinEntityIfNeeded(
    page: Page,
    entityName: string,
    credentials: Record<string, string>,
) {
    await goToIntegrations(page)

    const entityCard = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchBtn = entityCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchBtn
        .isVisible({ timeout: 2_000 })
        .catch(() => false)

    if (!isConnected) {
        await page.getByText(entityName).first().click()
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 10_000 })
        for (const [field, value] of Object.entries(credentials)) {
            await page.locator(`#${field}`).fill(value)
        }
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        await enterPinAndSubmit(page, MOCK_PIN_CODE)

        await expect(
            page.getByText(`Successfully logged in to ${entityName}`),
        ).toBeVisible({ timeout: 15_000 })

        await page.reload()
        await page.waitForLoadState('networkidle')
    }
}

async function enterPinAndSubmit(page: Page, pin: string) {
    for (const digit of pin) {
        await page.getByRole('button', { name: digit, exact: true }).click()
    }
    await page.getByRole('button', { name: 'Submit' }).click()
}

async function dismissDropdownOverlay(page: Page) {
    await page.evaluate(() => {
        document.querySelectorAll('div.fixed').forEach((el) => {
            if (
                el instanceof HTMLElement &&
                el.classList.contains('inset-0') &&
                el.classList.contains('z-40')
            ) {
                el.click()
            }
        })
    })
    await page.waitForTimeout(300)
}

const SIMPLE_CREDENTIALS = {
    user: 'test@example.com',
    password: 'MockPassword123',
}

test.describe('Multi-Scrape - Simple Entities', () => {
    test('rapid refresh of multiple simple entities', async ({
        authenticatedPage: page,
    }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', SIMPLE_CREDENTIALS)
        await connectEntityIfNeeded(page, 'Freedom24', SIMPLE_CREDENTIALS)

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

        await page.waitForTimeout(800)

        await page.locator('button[aria-label="Refresh Freedom24"]').click()
        await expect(
            page.getByText('Data successfully fetched from Freedom24'),
        ).toBeVisible({ timeout: 30_000 })

        await dismissDropdownOverlay(page)
    })
})

test.describe('Multi-Scrape - 2FA PIN Queue', () => {
    test('refresh multiple 2FA entities queues PINs and auto-advances', async ({
        authenticatedPage: page,
    }) => {
        await connectPinEntityIfNeeded(page, 'Wecity', SIMPLE_CREDENTIALS)
        await connectPinEntityIfNeeded(page, 'SEGO', SIMPLE_CREDENTIALS)

        await page.getByRole('button', { name: 'Summary' }).click()
        await page
            .getByRole('heading', { name: 'Summary' })
            .waitFor({ timeout: 10_000 })

        await page.getByRole('button', { name: 'Data' }).click()
        await page
            .locator('button[aria-label="Refresh Wecity"]')
            .waitFor({ timeout: 5_000 })

        // Trigger first 2FA refresh — PinPad modal will appear
        await page.locator('button[aria-label="Refresh Wecity"]').click()

        await expect(
            page.getByRole('heading', {
                name: 'Enter 6-digit code for Wecity',
            }),
        ).toBeVisible({ timeout: 15_000 })

        // Wait for cooldown then trigger second 2FA refresh via dispatchEvent
        // (PinPad modal at z-[60] blocks normal clicks on the dropdown at z-50)
        await page.waitForTimeout(800)
        await page
            .locator('button[aria-label="Refresh SEGO"]')
            .dispatchEvent('click')

        // Verify blue banner shows SEGO as pending
        const banner = page.locator('.bg-blue-50')
        await expect(banner).toBeVisible({ timeout: 10_000 })
        await expect(banner.getByRole('button', { name: 'SEGO' })).toBeVisible()

        // Submit PIN for Wecity
        await enterPinAndSubmit(page, MOCK_PIN_CODE)
        await expect(
            page.getByText('Data successfully fetched from Wecity'),
        ).toBeVisible({ timeout: 30_000 })

        // PinPad should auto-advance to SEGO
        await expect(
            page.getByRole('heading', { name: 'Enter 6-digit code for SEGO' }),
        ).toBeVisible({ timeout: 10_000 })

        // Blue banner should be gone (no more pending entities)
        await expect(banner).not.toBeVisible({ timeout: 5_000 })

        // Submit PIN for SEGO
        await enterPinAndSubmit(page, MOCK_PIN_CODE)
        await expect(
            page.getByText('Data successfully fetched from SEGO'),
        ).toBeVisible({ timeout: 30_000 })
    })
})

test.describe('Multi-Scrape - Mixed Simple and 2FA', () => {
    test('simple entities complete while 2FA entities queue in PinPad', async ({
        authenticatedPage: page,
    }) => {
        await connectEntityIfNeeded(page, 'Urbanitae', SIMPLE_CREDENTIALS)
        await connectPinEntityIfNeeded(page, 'Wecity', SIMPLE_CREDENTIALS)
        await connectPinEntityIfNeeded(page, 'SEGO', SIMPLE_CREDENTIALS)

        await page.getByRole('button', { name: 'Summary' }).click()
        await page
            .getByRole('heading', { name: 'Summary' })
            .waitFor({ timeout: 10_000 })

        await page.getByRole('button', { name: 'Data' }).click()
        await page
            .locator('button[aria-label="Refresh Urbanitae"]')
            .waitFor({ timeout: 5_000 })

        // Simple entity completes immediately
        await page.locator('button[aria-label="Refresh Urbanitae"]').click()
        await expect(
            page.getByText('Data successfully fetched from Urbanitae'),
        ).toBeVisible({ timeout: 30_000 })

        // First 2FA entity — PinPad appears
        await page.waitForTimeout(800)
        await page.locator('button[aria-label="Refresh Wecity"]').click()
        await expect(
            page.getByRole('heading', {
                name: 'Enter 6-digit code for Wecity',
            }),
        ).toBeVisible({ timeout: 15_000 })

        // Second 2FA entity — queued behind Wecity
        await page.waitForTimeout(800)
        await page
            .locator('button[aria-label="Refresh SEGO"]')
            .dispatchEvent('click')

        // Verify queue banner
        const banner = page.locator('.bg-blue-50')
        await expect(banner).toBeVisible({ timeout: 10_000 })
        await expect(banner.getByRole('button', { name: 'SEGO' })).toBeVisible()

        // Complete Wecity
        await enterPinAndSubmit(page, MOCK_PIN_CODE)
        await expect(
            page.getByText('Data successfully fetched from Wecity'),
        ).toBeVisible({ timeout: 30_000 })

        // Auto-advance to SEGO
        await expect(
            page.getByRole('heading', { name: 'Enter 6-digit code for SEGO' }),
        ).toBeVisible({ timeout: 10_000 })

        // Complete SEGO
        await enterPinAndSubmit(page, MOCK_PIN_CODE)
        await expect(
            page.getByText('Data successfully fetched from SEGO'),
        ).toBeVisible({ timeout: 30_000 })
    })
})
