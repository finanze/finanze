import { expect, type Page } from '@playwright/test'

export type EditMode = 'DRAFT' | 'QUICK'

export async function ensureEditMode(page: Page, mode: EditMode) {
    await page.locator('button[aria-label="Settings"]').first().click()
    await expect(
        page.getByRole('heading', { name: 'Settings' }).first(),
    ).toBeVisible({ timeout: 10_000 })

    const editMode = page.getByTestId('edit-mode')
    await expect(editMode).toBeVisible({ timeout: 10_000 })
    const option = editMode.getByTestId(`edit-mode-${mode}`)
    await expect(option).toBeVisible({ timeout: 10_000 })
    await option.click()
    await expect(option.locator('input')).toBeChecked()

    // General settings persist with a 500 ms debounce before navigation.
    await page.waitForTimeout(600)
}
