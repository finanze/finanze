import { expect } from '@playwright/test'
import { test } from '../../fixtures/fresh-page'
import { TEST_PASSWORD } from '../../helpers/constants'
import { setupCloudMocks, clearCloudMocks } from '../../helpers/cloud-mocks'
import type { Page } from '@playwright/test'

async function fillOrVerifyUsername(page: Page, value: string) {
    const input = page.locator('#restoreUsername')
    if (await input.isEnabled()) {
        await page.fill('#restoreUsername', value)
    } else {
        await expect(input).toHaveValue(value)
    }
}

test.describe('Cloud Restore - Navigation', () => {
    test('open cloud restore from signup and go back', async ({
        freshPage: page,
    }) => {
        await page.getByText('Have a Cloud account? Restore your data').click()

        await expect(page.getByText('Restore from Cloud')).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.locator('input[type="email"]')).toBeVisible()

        await page.getByText('Back to sign up').click()

        await expect(page.locator('#username')).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.locator('#password')).toBeVisible()
    })
})

test.describe('Cloud Restore - Cloud Login Errors', () => {
    test('invalid cloud credentials shows error', async ({
        freshPage: page,
    }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'invalid_credentials',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'wrongpassword')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await expect(page.getByText('Invalid email or password')).toBeVisible({
            timeout: 5_000,
        })

        await clearCloudMocks(page)
    })

    test('no backups found shows message and returns to cloud login', async ({
        freshPage: page,
    }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'success',
            backups: 'empty',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'password123')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await expect(
            page.getByText('No backups found for this account'),
        ).toBeVisible({ timeout: 10_000 })

        await expect(page.locator('input[type="email"]')).toBeVisible()

        await clearCloudMocks(page)
    })
})

test.describe('Cloud Restore - Credentials and Import', () => {
    test('backup found shows credentials form', async ({ freshPage: page }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'success',
            backups: 'with_data',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'password123')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await expect(page.getByText('Backup found!')).toBeVisible({
            timeout: 10_000,
        })
        await expect(page.locator('#restoreUsername')).toBeVisible()
        await expect(page.locator('#encryptionKey')).toBeVisible()
        await expect(
            page.getByText('This is the encryption key you used in the app'),
        ).toBeVisible()

        await clearCloudMocks(page)
    })

    test('wrong encryption key shows error and allows retry', async ({
        freshPage: page,
    }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'success',
            backups: 'with_data',
            cloudAuth: 'success',
            import: 'invalid_credentials',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'password123')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await page.locator('#restoreUsername').waitFor({ timeout: 10_000 })
        await fillOrVerifyUsername(page, 'restoreuser')
        await page.fill('#encryptionKey', 'WrongKey123!')
        await page.getByRole('button', { name: 'Restore data' }).click()

        await expect(
            page.getByText(
                'Invalid encryption key. Please check and try again.',
            ),
        ).toBeVisible({ timeout: 10_000 })

        await expect(page.locator('#encryptionKey')).toBeVisible()
        await expect(
            page.getByRole('button', { name: 'Restore data' }),
        ).toBeVisible()

        await clearCloudMocks(page)
    })

    test('back from credentials returns to signup', async ({
        freshPage: page,
    }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'success',
            backups: 'with_data',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'password123')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await page.locator('#restoreUsername').waitFor({ timeout: 10_000 })
        await expect(page.getByText('Backup found!')).toBeVisible()

        await page.getByText('Back to sign up').click()

        await expect(page.locator('#username')).toBeVisible({
            timeout: 5_000,
        })
        await expect(page.locator('#password')).toBeVisible()

        await clearCloudMocks(page)
    })

    test('full restore success shows importing state', async ({
        freshPage: page,
    }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'success',
            backups: 'with_data',
            cloudAuth: 'success',
            import: 'success',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'password123')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await page.locator('#restoreUsername').waitFor({ timeout: 10_000 })
        await fillOrVerifyUsername(page, 'restoreuser')
        await page.fill('#encryptionKey', TEST_PASSWORD)
        await page.getByRole('button', { name: 'Restore data' }).click()

        await expect(page.getByText('Restoring data...')).toBeVisible({
            timeout: 10_000,
        })
        await expect(
            page.getByText("Please don't close the app during this process"),
        ).toBeVisible()

        await clearCloudMocks(page)
    })

    test('cloud restore wrong key then exit and signup normally', async ({
        freshPage: page,
    }) => {
        await setupCloudMocks(page, {
            supabaseAuth: 'success',
            backups: 'with_data',
            cloudAuth: 'success',
            import: 'invalid_credentials',
        })

        await page.getByText('Have a Cloud account? Restore your data').click()
        await page.locator('input[type="email"]').waitFor({ timeout: 5_000 })

        await page.fill('input[type="email"]', 'test@example.com')
        await page.fill('input[type="password"]', 'password123')
        await page.getByRole('button', { name: 'Sign in with Email' }).click()

        await page.locator('#restoreUsername').waitFor({ timeout: 10_000 })
        await fillOrVerifyUsername(page, 'restoreuser')
        await page.fill('#encryptionKey', 'WrongKey123!')
        await page.getByRole('button', { name: 'Restore data' }).click()

        await expect(page.getByText('Invalid encryption key')).toBeVisible({
            timeout: 10_000,
        })

        await page.getByText('Back to sign up').click()

        await expect(page.locator('#username')).toBeVisible({
            timeout: 5_000,
        })

        const signupUsername = page.locator('#username')
        if (await signupUsername.isEnabled()) {
            await page.fill('#username', 'newuser')
        }
        await page.fill('#password', TEST_PASSWORD)
        await page.fill('#repeatPassword', TEST_PASSWORD)
        await page.locator('button[type="submit"]').click()

        await expect(
            page.getByRole('heading', { name: 'Summary' }),
        ).toBeVisible({ timeout: 10_000 })

        await clearCloudMocks(page)
    })
})
