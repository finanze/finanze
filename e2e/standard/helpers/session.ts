import type { Page } from '@playwright/test'
import { TEST_PASSWORD, TEST_USER } from './constants'

export const SESSION_STORAGE_KEY = 'finanze_api_session'

export async function sessionHeaders(
    page: Page,
): Promise<Record<string, string>> {
    const token = await page.evaluate(
        (key) => sessionStorage.getItem(key),
        SESSION_STORAGE_KEY,
    )
    return token ? { Authorization: `Bearer ${token}` } : {}
}

export async function lockBackend(backendUrl: string): Promise<void> {
    const logout = await fetch(`${backendUrl}/api/v1/logout`, {
        method: 'POST',
    }).catch(() => null)
    if (logout?.status !== 401) return

    const login = await fetch(`${backendUrl}/api/v1/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: TEST_USER, password: TEST_PASSWORD }),
    })
    if (login.status !== 200) return

    const { token } = await login.json()
    await fetch(`${backendUrl}/api/v1/logout`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` },
    })
}
