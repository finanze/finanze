import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import en from '../../../../frontend/app/src/i18n/locales/en.json' with { type: 'json' }

test('manages account exclusions without fetching and keeps changes when navigating', async ({
    authenticatedPage: page,
}) => {
    const copy = en.settings.assets.accounts
    const fetches: string[] = []
    page.on('request', request => {
        if (request.url().includes('/data/fetch')) fetches.push(request.url())
    })
    const openAccounts = async () => {
        await page.locator('button[aria-label="Settings"]').first().click()
        await page.getByRole('button', { name: /Accounts/ }).click()
    }
    await openAccounts()
    await expect(page.getByText(copy.emptyState, { exact: true })).toBeVisible()
    await expect(page.getByText(copy.dataUnchanged, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: copy.addIban }).click()
    const input = page.getByLabel(copy.ibanLabel)
    await input.fill('ES-invalid')
    await input.press('Enter')
    await expect(page.getByRole('alert')).toHaveText(copy.invalidIban)
    await input.fill(' es12 3456 7890 ')
    await page.getByRole('button', { name: copy.addIban }).click()
    await expect(page.getByText('ES12 3456 7890', { exact: true })).toBeVisible()
    await expect(page.getByText(copy.rulesChanged, { exact: true })).toBeVisible()
    await page.getByRole('button', { name: copy.addIban }).click()
    await input.fill('ES1234567890')
    await input.press('Enter')
    await expect(page.getByRole('alert')).toHaveText(copy.duplicateIban)
    await input.press('Escape')
    await page.getByRole('button', { name: copy.editIban }).click()
    await input.fill('ES999')
    await page.getByRole('button', { name: copy.saveIban }).click()
    await expect(page.getByText('ES99 9', { exact: true })).toBeVisible()
    await page
        .getByRole('navigation')
        .getByRole('button', { name: 'Integrations', exact: true })
        .click()
    await expect(page.getByRole('heading', { name: 'Integrations' }).first()).toBeVisible()
    await openAccounts()
    await expect(page.getByText('ES99 9', { exact: true })).toBeVisible()
    await page.getByRole('button', { name: copy.removeIban }).click()
    await expect(page.getByText(copy.emptyState, { exact: true })).toBeVisible()
    expect(fetches).toHaveLength(0)
})
