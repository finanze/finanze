import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { MOCK_PIN_CODE } from '../../helpers/constants'

test.describe('Connect Entity - 2FA/PIN (Trade Republic)', () => {
    test('connect entity with PIN verification', async ({
        authenticatedPage: page,
    }) => {
        // Navigate to entities via sidebar
        await page.getByRole('button', { name: 'Integrations' }).click()

        // Wait for entity list
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Click on Trade Republic (requires phone + PIN, then 4-digit code)
        await page.getByText('Trade Republic').first().click()

        // Login form should appear
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        // Fill credentials (Trade Republic: phone=PHONE, password=PIN)
        await page.locator('#phone').fill('+34612345678')
        await page.locator('#password').fill('1234')

        // Submit initial credentials
        await page.getByRole('button', { name: 'Submit' }).click()

        // Mock returns CODE_REQUESTED -> PIN pad should appear
        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        // Enter correct PIN via number pad buttons
        for (const digit of MOCK_PIN_CODE) {
            await page.getByRole('button', { name: digit, exact: true }).click()
        }

        // Submit the PIN
        await page.getByRole('button', { name: 'Submit' }).click()

        // Wait for success toast
        await expect(
            page.getByText('Successfully logged in to Trade Republic'),
        ).toBeVisible({ timeout: 15_000 })
    })

    test('wrong PIN shows error message', async ({
        authenticatedPage: page,
    }) => {
        // Navigate to entities via sidebar
        await page.getByRole('button', { name: 'Integrations' }).click()

        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Trade Republic may already be connected from previous test — click Relogin if visible
        const reloginButton = page.getByRole('button', { name: 'Relogin' })
        if (await reloginButton.isVisible().catch(() => false)) {
            await reloginButton.click()
        } else {
            await page.getByText('Trade Republic').first().click()
        }

        // Credentials form appears (even on Relogin)
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        await page.locator('#phone').fill('+34612345678')
        await page.locator('#password').fill('1234')
        await page.getByRole('button', { name: 'Submit' }).click()

        // PIN pad should appear
        await expect(page.getByText(/Enter \d+-digit code for/)).toBeVisible({
            timeout: 10_000,
        })

        // Enter wrong PIN via number pad buttons
        for (const digit of '9999') {
            await page.getByRole('button', { name: digit, exact: true }).click()
        }
        await page.getByRole('button', { name: 'Submit' }).click()

        // Error should appear in the PIN pad
        await expect(
            page.getByText('Invalid code provided').first(),
        ).toBeVisible({
            timeout: 5_000,
        })
    })
})
