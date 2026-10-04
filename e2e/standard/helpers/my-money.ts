import type { Page } from '@playwright/test'

export async function navigateToMyMoneyPage(
    page: Page,
    name: 'Activity' | 'Recurring' | 'Pending',
) {
    const navigation = page.getByRole('navigation')
    const destination = navigation.getByRole('button', { name, exact: true })
    if (!(await destination.isVisible())) {
        await navigation
            .getByRole('button', { name: 'My Money', exact: true })
            .click()
    }
    await destination.click()
}
