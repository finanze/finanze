import { expect, type Page } from '@playwright/test'

export async function navigateToMyMoneyPage(
    page: Page,
    name: 'Activity' | 'Budget' | 'Pending',
) {
    const navigation = page.getByRole('navigation')
    const destination = navigation.getByRole('button', { name, exact: true })
    const myMoney = navigation.getByRole('button', {
        name: 'My Money',
        exact: true,
    })
    await expect(myMoney).toBeVisible()
    if ((await myMoney.getAttribute('aria-expanded')) !== 'true') {
        await myMoney.click()
    }
    await destination.click()
}
