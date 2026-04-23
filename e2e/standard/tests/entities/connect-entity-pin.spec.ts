import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { MOCK_PIN_CODE } from '../../helpers/constants'

test.describe('Connect Entity - 2FA/PIN (Wecity)', () => {
    test('connect entity with PIN verification', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        await page.getByText('Wecity').first().click()

        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        await page.locator('#user').fill('test@example.com')
        await page.locator('#password').fill('MockPassword123')

        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        for (const digit of MOCK_PIN_CODE) {
            await page
                .getByRole('button', { name: digit, exact: true })
                .click()
        }

        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(
            page.getByText('Successfully logged in to Wecity'),
        ).toBeVisible({ timeout: 15_000 })
    })

    test('wrong PIN shows error message', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        const reloginButton = page.getByRole('button', { name: 'Relogin' })
        if (await reloginButton.isVisible().catch(() => false)) {
            await reloginButton.click()
        } else {
            await page.getByText('Wecity').first().click()
        }

        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        await page.locator('#user').fill('test@example.com')
        await page.locator('#password').fill('MockPassword123')
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        for (const digit of '999999') {
            await page
                .getByRole('button', { name: digit, exact: true })
                .click()
        }
        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(
            page.getByText('Invalid code provided').first(),
        ).toBeVisible({
            timeout: 5_000,
        })
    })
})
