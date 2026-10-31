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

        const categories = page.getByTestId('mcp-tool-categories')
        await expect(categories).toHaveAttribute('aria-expanded', 'false')
        await categories.click()
        await page
            .getByRole('button', {
                name: 'Read tools in Positions & Net Worth',
                exact: true,
            })
            .click()
        const readToolNames = page.getByRole('dialog', {
            name: 'Read tools in Positions & Net Worth',
            exact: true,
        })
        await expect(readToolNames).toContainText('get_historic_positions')
        await expect(readToolNames).toContainText('list_pending_flows')
        await expect(readToolNames).not.toContainText('save_manual_position')
        await page.keyboard.press('Escape')
        await expect(readToolNames).toBeHidden()
        await page
            .getByRole('button', {
                name: 'Read tools in Essential',
                exact: true,
            })
            .click()
        const essentialToolNames = page.getByRole('dialog', {
            name: 'Read tools in Essential',
            exact: true,
        })
        await expect(essentialToolNames.locator('code')).toHaveText([
            'get_context',
            'list_entities',
        ])
        await page.keyboard.press('Escape')
        const positionsRead = page.getByTestId('mcp-category-positions-read')
        const positionsWrite = page.getByTestId('mcp-category-positions-write')
        const budgetRead = page.getByTestId('mcp-category-budget-read')
        await positionsRead.click()
        await expect(positionsRead).toHaveAttribute('data-state', 'unchecked')
        await expect(positionsWrite).toHaveAttribute('data-state', 'unchecked')
        await page
            .getByRole('button', {
                name: 'Write tools in Positions & Net Worth',
                exact: true,
            })
            .click()
        const writeToolNames = page.getByRole('dialog', {
            name: 'Write tools in Positions & Net Worth',
            exact: true,
        })
        await expect(writeToolNames).toContainText('settle_pending_flow')
        await expect(writeToolNames).toContainText('save_commodities')
        await expect(writeToolNames).not.toContainText('get_positions')
        await page.keyboard.press('Escape')
        const withoutPositions = await listTools(page, token)
        expect(withoutPositions.tools).not.toContain('get_positions')
        expect(withoutPositions.tools).not.toContain('get_historic_positions')
        expect(withoutPositions.tools).not.toContain('list_pending_flows')
        expect(withoutPositions.tools).toContain('get_contributions')
        expect(withoutPositions.tools).toContain('get_context')
        expect(withoutPositions.tools).toContain('list_entities')

        await positionsWrite.click()
        await expect(positionsRead).toHaveAttribute('data-state', 'checked')
        await expect(positionsWrite).toHaveAttribute('data-state', 'checked')
        expect((await listTools(page, token)).tools).toContain(
            'settle_pending_flow',
        )
        await positionsWrite.click()
        await expect(positionsWrite).toHaveAttribute('data-state', 'unchecked')
        const positionsReadOnly = await listTools(page, token)
        expect(positionsReadOnly.tools).toContain('get_historic_positions')
        expect(positionsReadOnly.tools).not.toContain('settle_pending_flow')

        await budgetRead.click()
        await expect(budgetRead).toHaveAttribute('data-state', 'unchecked')
        const withoutBudget = await listTools(page, token)
        expect(withoutBudget.tools).not.toContain('get_contributions')
        expect(withoutBudget.tools).not.toContain('save_contribution')
        expect(withoutBudget.tools).not.toContain('list_periodic_flows')
        expect(withoutBudget.tools).toContain('get_positions')

        await page.getByRole('tab', { name: 'General', exact: true }).click()
        await page.getByRole('tab', { name: 'MCP', exact: true }).click()
        await expect(categories).toHaveAttribute('aria-expanded', 'false')
        await categories.click()
        await expect(budgetRead).toHaveAttribute('data-state', 'unchecked')
        await expect(positionsWrite).toHaveAttribute('data-state', 'unchecked')
        await readOnly.click()
        await expect(readOnly).toHaveAttribute('data-state', 'checked')
        await expect(positionsWrite).toBeDisabled()
        await expect(
            page.getByTestId('mcp-category-transactions-write'),
        ).toHaveAttribute('data-state', 'checked')
        expect((await listTools(page, token)).tools).not.toContain('save_label')
        await readOnly.click()
        await expect(readOnly).toHaveAttribute('data-state', 'unchecked')
        await expect(positionsWrite).toHaveAttribute('data-state', 'unchecked')
        expect((await listTools(page, token)).tools).toContain('save_label')

        await page.getByTestId('mcp-categories-reset').click()
        await expect(budgetRead).toHaveAttribute('data-state', 'checked')
        await expect(positionsWrite).toHaveAttribute('data-state', 'checked')
        await expect(page.getByTestId('mcp-categories-reset')).toBeDisabled()
        expect((await listTools(page, token)).tools.sort()).toEqual(
            readWrite.tools.sort(),
        )

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
