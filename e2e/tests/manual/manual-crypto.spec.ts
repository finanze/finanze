import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'

const BINANCE_CREDENTIALS = {
    apiKey: 'mock-api-key',
    secretKey: 'mock-secret-key',
}

const URBANITAE_CREDENTIALS = {
    user: 'test@example.com',
    password: 'MockPassword123',
}

async function connectAndFetchBinance(page: Page) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

    const cancelBtn = page.getByRole('button', { name: 'Cancel' })
    if (await cancelBtn.isVisible({ timeout: 1_000 }).catch(() => false)) {
        await cancelBtn.click()
        await page.waitForTimeout(500)
    }

    // Use exact match to avoid matching "Binance Smart Chain"
    const binanceCard = page
        .locator('h3')
        .filter({ has: page.locator('span:text-is("Binance")') })
        .first()
        .locator('../..')
    const fetchBtn = binanceCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchBtn
        .isVisible({ timeout: 3_000 })
        .catch(() => false)

    if (!isConnected) {
        const binanceText = page.locator('span:text-is("Binance")').first()
        await binanceText.scrollIntoViewIfNeeded()
        await page.waitForTimeout(300)
        await binanceText.click()
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 10_000 })
        await page.locator('#apiKey').fill(BINANCE_CREDENTIALS.apiKey)
        await page.locator('#secretKey').fill(BINANCE_CREDENTIALS.secretKey)
        await page.getByRole('button', { name: 'Submit' }).click()
        await expect(
            page.getByText('Successfully logged in to Binance'),
        ).toBeVisible({ timeout: 15_000 })

        // Navigate back to Integrations to find the Fetch button
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }

    // Fetch data — re-locate the card after potential reload
    const card = page
        .locator('h3')
        .filter({ has: page.locator('span:text-is("Binance")') })
        .first()
        .locator('../..')
    const fetchButton = card.getByRole('button', { name: 'Fetch' })
    if (await fetchButton.isVisible({ timeout: 2_000 }).catch(() => false)) {
        await fetchButton.scrollIntoViewIfNeeded()
        await fetchButton.click()
        await expect(
            page.getByText('Select features to fetch from Binance'),
        ).toBeVisible({ timeout: 5_000 })
        await expect(
            page.getByRole('button', { name: 'Fetch data' }),
        ).toBeEnabled({ timeout: 5_000 })
        await page.getByRole('button', { name: 'Fetch data' }).click()
        await expect(
            page.getByText('Data successfully fetched from Binance'),
        ).toBeVisible({ timeout: 15_000 })
        const cancel = page.getByRole('button', { name: 'Cancel' })
        if (await cancel.isVisible({ timeout: 2_000 }).catch(() => false)) {
            await cancel.click()
            await page.waitForTimeout(500)
        }
    }
}

async function connectEntityIfNeeded(
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
        // Navigate back to Integrations to find the Fetch button
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }
}

async function setupCryptoMocks(page: Page) {
    // Mock search: GET /api/v1/assets/crypto?symbol=... or ?name=...
    await page.route('**/api/v1/assets/crypto?**', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                provider: 'coingecko',
                assets: [
                    {
                        name: 'Litecoin',
                        symbol: 'LTC',
                        platforms: [],
                        provider: 'coingecko',
                        provider_id: 'litecoin',
                    },
                ],
                page: 1,
                limit: 25,
                total: 1,
            }),
        })
    })

    // Mock details: GET /api/v1/assets/crypto/<id>?provider=coingecko
    await page.route('**/api/v1/assets/crypto/litecoin**', async (route) => {
        await route.fulfill({
            status: 200,
            contentType: 'application/json',
            body: JSON.stringify({
                name: 'Litecoin',
                symbol: 'LTC',
                platforms: [],
                provider: 'coingecko',
                provider_id: 'litecoin',
                price: { usd: 80, eur: 73 },
                icon_url: null,
            }),
        })
    })
}

async function navigateToCrypto(page: Page) {
    // Navigate via sidebar: expand My Assets, then click Crypto button
    const myAssets = page.getByRole('button', { name: 'My Assets' })
    await myAssets.click()
    await page.waitForTimeout(300)
    await page.getByRole('button', { name: 'Crypto' }).click()
    await page
        .getByRole('heading', { name: 'Crypto' })
        .first()
        .waitFor({ timeout: 15_000 })
    await page.waitForTimeout(2_000)
}

async function saveDraftAndPersist(page: Page) {
    // Click form Save inside the dialog overlay
    const dialog = page.locator('.fixed.inset-0').last()
    await dialog.getByRole('button', { name: 'Save' }).click()

    // Wait for dialog to fully close and state to propagate
    await page.waitForTimeout(1_500)

    // Wait for the "unsaved changes" indicator to confirm draft was saved
    await expect(
        page.getByText('You have unsaved changes'),
    ).toBeVisible({ timeout: 5_000 })

    // Click page-level Save button
    const saveBtn = page.getByTestId('save-positions')
    await expect(saveBtn).toBeEnabled({ timeout: 3_000 })
    await saveBtn.click()
    await expect(
        page.getByText('Manual positions saved successfully.'),
    ).toBeVisible({ timeout: 10_000 })
}

async function searchAndSelectCryptoAsset(page: Page) {
    // Search for crypto by symbol
    await page.locator('#symbol').fill('LTC')
    await page.locator('#symbol').press('Enter')

    // Wait for search dropdown (portaled to body at z-[99999])
    const dropdown = page.locator('.fixed').filter({
        has: page.getByText('Litecoin'),
    })
    await dropdown.getByText('Litecoin').first().click({ timeout: 10_000 })
    await page.waitForTimeout(500)
}

async function addManualCryptoPosition(page: Page) {
    await page.getByRole('button', { name: 'Add' }).click()
    await expect(page.getByText('Add manual crypto')).toBeVisible({
        timeout: 5_000,
    })

    await searchAndSelectCryptoAsset(page)

    // Select an existing entity for the manual position
    await page.locator('#entity_id').selectOption({ label: 'Urbanitae' })

    // Fill amount
    await page.locator('#amount').fill('5')
    await page.locator('#initial_investment').fill('400')

    await saveDraftAndPersist(page)

    // Verify manual LTC position appears
    await expect(page.getByText('Litecoin').first()).toBeVisible({
        timeout: 10_000,
    })
}

test.describe('Manual Crypto Positions', () => {
    test('create a manual crypto position', async ({
        authenticatedPage: page,
    }) => {
        // Connect Binance for fetched crypto data + Urbanitae for manual positions
        await connectAndFetchBinance(page)
        await connectEntityIfNeeded(page, 'Urbanitae', URBANITAE_CREDENTIALS)

        await setupCryptoMocks(page)
        await navigateToCrypto(page)

        // Binance fetched crypto should be visible
        await expect(page.getByText('Bitcoin').first()).toBeVisible({
            timeout: 10_000,
        })

        // Add manual LTC position under Urbanitae entity
        await addManualCryptoPosition(page)

        // Verify Binance fetched BTC/ETH still visible
        await expect(page.getByText('Bitcoin').first()).toBeVisible()
    })

    test('edit a manual crypto position', async ({
        authenticatedPage: page,
    }) => {
        // Must connect+fetch Binance so crypto page has data
        await connectAndFetchBinance(page)
        await connectEntityIfNeeded(page, 'Urbanitae', URBANITAE_CREDENTIALS)

        await setupCryptoMocks(page)
        await navigateToCrypto(page)

        // Create a manual position if not present (self-contained)
        const hasLtc = await page
            .getByText('Litecoin')
            .first()
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!hasLtc) {
            await addManualCryptoPosition(page)
        }

        // Enter edit mode
        await page.getByRole('button', { name: 'Edit' }).click()
        await page.waitForTimeout(300)

        // Find the manual position's inline edit button (icon-only with pencil)
        const editBtn = page.locator(
            'button:has(.lucide-pen-line), button:has(.lucide-pencil)',
        )
        await editBtn.last().click()
        await page.waitForTimeout(300)

        await expect(page.getByText('Edit manual crypto')).toBeVisible({
            timeout: 5_000,
        })

        // Change amount
        await page.locator('#amount').fill('10')

        await saveDraftAndPersist(page)
    })

    test('delete a manual crypto position', async ({
        authenticatedPage: page,
    }) => {
        // Must connect+fetch Binance so crypto page has data
        await connectAndFetchBinance(page)
        await connectEntityIfNeeded(page, 'Urbanitae', URBANITAE_CREDENTIALS)

        await setupCryptoMocks(page)
        await navigateToCrypto(page)

        // Create a manual position if not present (self-contained)
        const hasLtc = await page
            .getByText('Litecoin')
            .first()
            .isVisible({ timeout: 3_000 })
            .catch(() => false)
        if (!hasLtc) {
            await addManualCryptoPosition(page)
        }

        // Enter edit mode
        await page.getByRole('button', { name: 'Edit' }).click()
        await page.waitForTimeout(300)

        // Click delete button (Trash2 icon, red) on the manual position
        const deleteBtn = page.locator(
            'button.text-red-500:has(.lucide-trash-2)',
        )
        await deleteBtn.last().click()

        // Confirmation dialog
        await expect(page.getByText('Delete manual position')).toBeVisible({
            timeout: 3_000,
        })
        await page
            .locator('.fixed.inset-0')
            .last()
            .getByRole('button', { name: 'Delete' })
            .click()
        await page.waitForTimeout(300)

        // Save
        await page.getByTestId('save-positions').click()
        await expect(
            page.getByText('Manual positions saved successfully.'),
        ).toBeVisible({ timeout: 10_000 })
    })

    test('fetched and manual crypto coexist', async ({
        authenticatedPage: page,
    }) => {
        // Must connect+fetch Binance so crypto page has data
        await connectAndFetchBinance(page)
        await connectEntityIfNeeded(page, 'Urbanitae', URBANITAE_CREDENTIALS)

        await setupCryptoMocks(page)
        await navigateToCrypto(page)

        // Binance fetched crypto should be visible
        await expect(page.getByText('Bitcoin').first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText('Ethereum').first()).toBeVisible()

        // Add a manual crypto position
        await addManualCryptoPosition(page)

        // All should coexist: fetched BTC/ETH + manual LTC
        await expect(page.getByText('Bitcoin').first()).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText('Ethereum').first()).toBeVisible()
        await expect(page.getByText('Litecoin').first()).toBeVisible()

        // Clean up: delete the manual position
        await page.getByRole('button', { name: 'Edit' }).click()
        await page.waitForTimeout(300)
        const deleteBtn = page.locator(
            'button.text-red-500:has(.lucide-trash-2)',
        )
        await deleteBtn.last().click()
        await expect(page.getByText('Delete manual position')).toBeVisible({
            timeout: 3_000,
        })
        await page
            .locator('.fixed.inset-0')
            .last()
            .getByRole('button', { name: 'Delete' })
            .click()
        await page.waitForTimeout(300)
        await page.getByTestId('save-positions').click()
        await expect(
            page.getByText('Manual positions saved successfully.'),
        ).toBeVisible({ timeout: 10_000 })
    })
})
