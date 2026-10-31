import { expect } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { navigateToMyMoneyPage } from '../../helpers/my-money'

test.describe('External labeling providers', () => {
    test('lists AI providers with icons and switches to OpenAI', async ({
        authenticatedPage: page,
    }) => {
        await navigateToMyMoneyPage(page, 'Activity')
        await page.getByRole('tab', { name: /Automation/ }).click()

        const card = page.getByTestId('external-labeling-card')
        await card.waitFor({ timeout: 10_000 })
        await card.getByTestId('external-labeling-switch').click()

        const trigger = card.locator('#external-provider')
        await expect(trigger).toBeVisible({ timeout: 10_000 })
        await expect(trigger.locator('img')).toHaveCount(1)
        await trigger.click()

        const openRouter = page.getByTestId(
            'external-provider-option-OPENROUTER',
        )
        const openAI = page.getByTestId('external-provider-option-OPENAI')
        await expect(openRouter).toBeVisible()
        await expect(openAI).toBeVisible()
        await expect(openAI).toContainText('OpenAI')
        await expect(openAI.locator('img')).toHaveAttribute(
            'src',
            'icons/external-integrations/OPENAI.png',
        )

        await openAI.click()
        await expect(openAI).toBeHidden()
        await expect(trigger).toContainText('OpenAI')
        await expect(card.getByText('GPT-6 Luna')).toBeVisible()
        await expect(
            card.getByText('gpt-6-luna', { exact: true }),
        ).toBeVisible()
        await expect(card.getByText('Not connected')).toBeVisible()

        await trigger.click()
        await page.getByTestId('external-provider-option-OPENROUTER').click()
        await expect(trigger).toContainText('OpenRouter')
        await expect(card.getByText('~typesafe/jev-latest')).toBeVisible()
    })
})
