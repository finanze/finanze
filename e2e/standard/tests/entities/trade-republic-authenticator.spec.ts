import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { TRADE_REPUBLIC_CREDENTIALS } from '../../helpers/constants'

test('connect and fetch Trade Republic with an authenticator', async ({
    authenticatedPage: page,
}) => {
    await page.getByRole('button', { name: 'Integrations' }).click()
    await expect(
        page.getByRole('heading', { name: 'Integrations' }),
    ).toBeVisible()

    const card = page
        .locator('h3')
        .filter({
            has: page.getByRole('img', { name: 'Trade Republic', exact: true }),
        })
        .first()
        .locator('../..')
    const relogin = card.getByRole('button', { name: 'Relogin' })
    if (await relogin.isVisible()) {
        await relogin.click()
    } else {
        await page.getByText('Trade Republic').first().click()
    }
    await expect(page.getByText('Enter credentials for')).toBeVisible()
    await page.locator('#phone').fill(TRADE_REPUBLIC_CREDENTIALS.phone)
    await page.locator('#password').fill('totp-e2e')
    await page.getByRole('button', { name: 'Submit' }).click()

    await expect(
        page.getByText('Enter the code from your authenticator app.'),
    ).toBeVisible()
    await page.getByLabel('Verification code').fill('999999')
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(page.getByText('Invalid code provided').first()).toBeVisible()
    await page.getByLabel('Verification code').fill('123456')
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(page.getByText('Confirm login in Trade Republic')).toBeVisible()
    await expect(
        page.getByText('Successfully logged in to Trade Republic'),
    ).toBeVisible()

    await card.getByRole('button', { name: 'Fetch' }).click()
    await expect(
        page.getByText('Select features to fetch from Trade Republic'),
    ).toBeVisible()
    await page.locator('.fixed').getByRole('button', { name: 'Fetch' }).click()

    await expect(
        page.getByText('Enter the code from your authenticator app.'),
    ).toBeVisible()
    await page.getByLabel('Verification code').fill('123456')
    await page.getByRole('button', { name: 'Submit' }).click()
    await expect(page.getByText('Confirm login in Trade Republic')).toBeVisible()
    await expect(
        page.getByText('Data successfully fetched from Trade Republic'),
    ).toBeVisible({ timeout: 30_000 })
})
