import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { ensureEditMode } from '../../helpers/edit-mode'
import { selectEntity } from '../../helpers/entity-selector'
import { navigateToMyMoneyPage } from '../../helpers/my-money'

const CREDENTIALS = {
    user: 'test@example.com',
    password: 'MockPassword123',
}

async function connectEntityIfNeeded(page: Page, entityName: string) {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await page
        .getByRole('heading', { name: 'Integrations' })
        .waitFor({ timeout: 15_000 })

    const entityCard = page
        .locator('h3', { hasText: entityName })
        .first()
        .locator('../..')
    const fetchButton = entityCard.getByRole('button', { name: 'Fetch' })
    const isConnected = await fetchButton
        .isVisible({ timeout: 3_000 })
        .catch(() => false)

    if (!isConnected) {
        await page.getByText(entityName).first().click()
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 10_000 })
        await page.locator('#user').fill(CREDENTIALS.user)
        await page.locator('#password').fill(CREDENTIALS.password)
        await page.getByRole('button', { name: 'Submit' }).click()
        await expect(
            page.getByText(`Successfully logged in to ${entityName}`),
        ).toBeVisible({ timeout: 15_000 })

        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })
    }
}

async function navigateToContributions(page: Page) {
    await navigateToMyMoneyPage(page, 'Recurring')
    await page.getByRole('tab', { name: /^Investments/ }).click()
    await expect(
        page.getByRole('heading', { name: 'Recurring', exact: true }),
    ).toBeVisible({ timeout: 10_000 })
}

test.describe('Manual Contributions - QUICK mode', () => {
    test.beforeEach(async ({ authenticatedPage: page }) => {
        await ensureEditMode(page, 'QUICK')
    })

    test('persists manual contribution changes immediately', async ({
        authenticatedPage: page,
    }) => {
        await connectEntityIfNeeded(page, 'Urbanitae')
        await navigateToContributions(page)

        const contributionName = 'E2E Quick Contribution'
        await page.getByRole('button', { name: 'New' }).click()
        const dialog = page.locator('.fixed.inset-0').last()
        await expect(dialog.getByText('Add contribution')).toBeVisible({
            timeout: 5_000,
        })
        const frequencyOptions = dialog.getByTestId(
            'contribution-frequency-options',
        )
        const monthlyFrequency = dialog.getByTestId(
            'contribution-frequency-option-monthly',
        )
        const biweeklyFrequency = dialog.getByTestId(
            'contribution-frequency-option-biweekly',
        )
        await expect(frequencyOptions.getByRole('button')).toHaveCount(7)
        await expect(monthlyFrequency).toHaveAttribute('aria-pressed', 'true')
        await biweeklyFrequency.click()
        await expect(biweeklyFrequency).toHaveAttribute('aria-pressed', 'true')
        await expect(monthlyFrequency).toHaveAttribute('aria-pressed', 'false')
        await monthlyFrequency.click()
        await expect(monthlyFrequency).toHaveAttribute('aria-pressed', 'true')
        await selectEntity(page, 'Urbanitae', { inDialog: true })
        await dialog.locator('#name').fill(contributionName)
        await dialog.locator('#target').fill('IE00B4L5Y983')
        await dialog.locator('#targetName').fill('E2E Quick Fund')
        await dialog.locator('#amount').fill('250')
        await dialog.getByRole('button', { name: 'Add' }).click()

        await expect(page.getByText('Saved successfully')).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(contributionName)).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByRole('button', { name: 'Done' })).toBeVisible()

        await page.locator('button[aria-label="Settings"]').first().click()
        await expect(
            page.getByRole('heading', { name: 'Settings' }).first(),
        ).toBeVisible({ timeout: 10_000 })
        await navigateToContributions(page)
        await expect(page.getByText(contributionName)).toBeVisible({
            timeout: 10_000,
        })

        await page.getByRole('button', { name: 'Edit' }).click()
        await expect(page.getByRole('button', { name: 'Done' })).toBeVisible()
        await page.locator('button[aria-label="Edit"]').last().click()
        const editDialog = page.locator('.fixed.inset-0').last()
        await expect(editDialog.getByText('Edit contribution')).toBeVisible({
            timeout: 5_000,
        })
        await editDialog.locator('#amount').fill('300')
        await editDialog.getByRole('button', { name: 'Save' }).click()

        await expect(page.getByText('Saved successfully')).toBeVisible({
            timeout: 10_000,
        })
        await page.getByRole('button', { name: 'Done' }).click()
        await page.getByRole('button', { name: 'Edit' }).click()
        await page.locator('button[aria-label="Delete"]').last().click()

        await expect(page.getByText('Saved successfully')).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.getByText(contributionName)).not.toBeVisible({
            timeout: 10_000,
        })
    })
})
