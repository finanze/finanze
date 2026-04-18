import type { Page } from '@playwright/test'

/**
 * Select an entity in the EntitySelector popover component.
 * Scopes to the last dialog overlay if inside a modal, otherwise uses the page.
 */
export async function selectEntity(
    page: Page,
    entityName: string,
    { inDialog = false }: { inDialog?: boolean } = {},
) {
    const scope = inDialog ? page.locator('.fixed.inset-0').last() : page
    const trigger = scope.getByRole('combobox').first()
    await trigger.click()
    await page.waitForTimeout(300)
    const popover = page.locator('[data-radix-popper-content-wrapper]').last()
    await popover.getByRole('button', { name: entityName }).click()
    await page.waitForTimeout(200)
}
