import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const CREDENTIALS = {
    user: 'test@example.com',
    password: 'MockPassword123',
}

async function connectAndFetchEntity(
    page: Page,
    entityName: string,
    credentials: Record<string, string>,
) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

    const cancelBtn = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await cancelBtn.click()
        await page.waitForTimeout(500)
    }

    const entityCard = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchBtn = entityCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchBtn
        .isVisible({ timeout: 3_000 })
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
        ).toBeVisible({ timeout: 15_000 })

        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }

    const card = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchButton = card.getByRole('button', { name: 'Fetch' })
    if (await fetchButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await fetchButton.click()
        await expect(
            page.getByText(`Select features to fetch from ${entityName}`),
        ).toBeVisible({ timeout: 5_000 })
        const modalFetch = page
            .locator('.fixed')
            .getByRole('button', { name: 'Fetch' })
        await expect(modalFetch).toBeEnabled({ timeout: 5_000 })
        await modalFetch.click()
        await expect(
            page.getByText(`Data successfully fetched from ${entityName}`),
        ).toBeVisible({ timeout: 15_000 })
        const cancel = page.getByRole('button', { name: 'Cancel' })
        if (await cancel.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await cancel.click()
            await page.waitForTimeout(500)
        }
    }
}

async function goToDashboard(page: Page) {
    const summaryBtn = page.getByRole('button', {
        name: 'Summary',
        exact: true,
    })
    if (await summaryBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await summaryBtn.click()
    }
    await expect(page.getByRole('heading', { name: 'Summary' })).toBeVisible({
        timeout: 10_000,
    })
    await page.waitForTimeout(500)
}

test.describe('Dashboard - Net Worth Timeline', () => {
    test('renders the timeline card and supports range switching and expand', async ({
        authenticatedPage: page,
    }) => {
        await connectAndFetchEntity(page, 'Urbanitae', CREDENTIALS)
        await goToDashboard(page)

        const title = page.getByText('Net Worth Timeline').first()
        await expect(title).toBeVisible({ timeout: 15_000 })

        // Quick range buttons are present and clickable
        const oneYear = page.getByRole('button', { name: '1Y', exact: true })
        const sixMonths = page.getByRole('button', { name: '6M', exact: true })
        const oneWeek = page.getByRole('button', { name: '1W', exact: true })
        await expect(oneYear).toBeVisible()
        await expect(sixMonths).toBeVisible()

        await sixMonths.click()
        await page.waitForTimeout(300)
        await oneWeek.click()
        await page.waitForTimeout(300)

        // Expand to fullscreen overlay and collapse back
        await page.getByRole('button', { name: 'Expand' }).click()
        const collapse = page.getByRole('button', { name: 'Collapse' })
        await expect(collapse).toBeVisible({ timeout: 5_000 })
        await collapse.click()
        await expect(collapse).not.toBeVisible({ timeout: 5_000 })
    })
})
