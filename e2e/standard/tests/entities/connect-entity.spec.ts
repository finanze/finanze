import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'

test.describe('Connect Entity - Simple Credentials (Urbanitae)', () => {
    test('connect entity with email and password', async ({
        authenticatedPage: page,
    }) => {
        // Navigate to entities via sidebar
        await page.getByRole('button', { name: 'Integrations' }).click()

        // Wait for entity list to load
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Click on Urbanitae entity card
        await page.getByText('Urbanitae').first().click()

        // Login form should appear with entity name
        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        // Fill credentials (Urbanitae: user=EMAIL, password=PASSWORD)
        await page.locator('#user').fill('test@example.com')
        await page.locator('#password').fill('MockPassword123')

        // Submit
        await page.getByRole('button', { name: 'Submit' }).click()

        // Wait for success toast
        await expect(
            page.getByText('Successfully logged in to Urbanitae'),
        ).toBeVisible({ timeout: 15_000 })

        // Navigate back to entities and verify connected badge
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        // Entity should show "Connected" heading section and badge
        await expect(page.getByText('Connected').first()).toBeVisible({
            timeout: 5_000,
        })
    })
})

test.describe('Connect Entity - API Credentials (Trading 212)', () => {
    test('connect entity with api key and secret key', async ({
        authenticatedPage: page,
    }) => {
        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        await page.getByText('Trading 212').first().scrollIntoViewIfNeeded()
        await page.getByText('Trading 212').first().click()

        await page
            .getByText('Enter credentials for')
            .waitFor({ timeout: 5_000 })

        await page.locator('#apiKey').fill('mock-api-key')
        await page.locator('#secretKey').fill('mock-secret-key')

        await page.getByRole('button', { name: 'Submit' }).click()

        await expect(
            page.getByText('Successfully logged in to Trading 212'),
        ).toBeVisible({ timeout: 15_000 })

        await page.getByRole('button', { name: 'Integrations' }).click()
        await page
            .getByRole('heading', { name: 'Integrations' })
            .waitFor({ timeout: 15_000 })

        await expect(page.getByText('Connected').first()).toBeVisible({
            timeout: 5_000,
        })
    })
})
