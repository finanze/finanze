import { expect, type Page } from '@playwright/test'
import { test } from '../../fixtures/auth'
import { BACKEND_URL } from '../../helpers/constants'

const MCP_URL = `${BACKEND_URL}/mcp`

async function listTools(page: Page, token?: string) {
    const headers: Record<string, string> = {
        Accept: 'application/json, text/event-stream',
    }
    if (token) headers.Authorization = `Bearer ${token}`
    const response = await page.request.post(MCP_URL, {
        headers,
        data: { jsonrpc: '2.0', id: 1, method: 'tools/list', params: {} },
    })
    if (!response.ok()) return { status: response.status(), tools: [] }
    const body = await response.json()
    return {
        status: response.status(),
        tools: body.result.tools.map((tool: { name: string }) => tool.name),
    }
}

test.describe('MCP server settings', () => {
    test('enables access, toggles modifications and rotates the token', async ({
        authenticatedPage: page,
    }) => {
        await page.locator('button[aria-label="Settings"]').first().click()
        await page.getByRole('tab', { name: 'MCP' }).click()

        const enabled = page.getByTestId('mcp-enabled')
        const readOnly = page.getByTestId('mcp-read-only')
        const tokenInput = page.getByTestId('mcp-token')

        await expect(enabled).toHaveAttribute('data-state', 'unchecked')
        await expect(readOnly).toBeDisabled()
        await expect(readOnly).toHaveAttribute('data-state', 'checked')
        await expect(tokenInput).toBeHidden()
        expect((await listTools(page)).status).toBe(404)

        await enabled.click()
        await expect(enabled).toHaveAttribute('data-state', 'checked')
        await expect(page.getByTestId('mcp-server-url')).toHaveValue(MCP_URL)

        const token = await tokenInput.inputValue()
        expect(token.length).toBeGreaterThan(20)

        const snippet = page.getByTestId('mcp-snippet')
        await expect(snippet).toContainText(MCP_URL)
        await expect(snippet).not.toContainText(token)
        await page.getByRole('button', { name: 'Claude Desktop' }).click()
        await expect(snippet).toContainText('mcp-remote')

        expect((await listTools(page)).status).toBe(401)
        expect((await listTools(page, 'wrong-token')).status).toBe(401)

        const readOnlyTools = await listTools(page, token)
        expect(readOnlyTools.status).toBe(200)
        expect(readOnlyTools.tools).toContain('get_net_worth')
        expect(readOnlyTools.tools).not.toContain('save_label')

        await readOnly.click()
        await expect(readOnly).toHaveAttribute('data-state', 'unchecked')
        await expect(page.getByText('Read-only mode is off.')).toBeVisible()

        const readWrite = await listTools(page, token)
        expect(readWrite.tools).toContain('get_net_worth')
        expect(readWrite.tools).toContain('save_label')

        await page.getByTestId('mcp-regenerate-token').click()
        await page
            .locator('div.fixed')
            .filter({ hasText: 'Regenerate access token?' })
            .getByRole('button', { name: 'Regenerate' })
            .click()
        await expect(tokenInput).not.toHaveValue(token)

        const newToken = await tokenInput.inputValue()
        expect((await listTools(page, token)).status).toBe(401)
        expect((await listTools(page, newToken)).status).toBe(200)

        await readOnly.click()
        await expect(readOnly).toHaveAttribute('data-state', 'checked')
        await enabled.click()
        await expect(enabled).toHaveAttribute('data-state', 'unchecked')
        await expect(tokenInput).toBeHidden()
        expect((await listTools(page, newToken)).status).toBe(404)
    })
})
