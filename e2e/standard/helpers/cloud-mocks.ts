import type { Page } from '@playwright/test'

export interface CloudMockOptions {
    supabaseAuth?: 'success' | 'invalid_credentials'
    backups?: 'with_data' | 'empty' | 'none'
    import?: 'success' | 'invalid_credentials' | 'invalid_then_success' | 'none'
    cloudAuth?: 'success' | 'none'
}

const SUPABASE_URL_PATTERN = '**/auth/v1/token**'

const MOCK_SUPABASE_SESSION = {
    access_token: 'mock-access-token-e2e',
    token_type: 'bearer',
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: 'mock-refresh-token-e2e',
    user: {
        id: 'mock-user-id-e2e',
        aud: 'authenticated',
        role: 'authenticated',
        email: 'test@example.com',
        email_confirmed_at: new Date().toISOString(),
        app_metadata: { provider: 'email', providers: ['email'] },
        user_metadata: {},
        identities: [
            {
                id: 'mock-identity-id',
                user_id: 'mock-user-id-e2e',
                identity_data: { email: 'test@example.com' },
                provider: 'email',
                created_at: new Date().toISOString(),
                updated_at: new Date().toISOString(),
            },
        ],
        created_at: new Date().toISOString(),
        updated_at: new Date().toISOString(),
    },
}

const MOCK_BACKUPS_WITH_DATA = {
    pieces: {
        data: {
            local: null,
            remote: {
                hash: 'abc123',
                size: 1024,
                last_modified: new Date().toISOString(),
            },
            last_update: new Date().toISOString(),
            has_local_changes: false,
            status: 'SYNCED',
        },
    },
}

const MOCK_BACKUPS_EMPTY = {
    pieces: {
        data: {
            local: null,
            remote: null,
            last_update: new Date().toISOString(),
            has_local_changes: false,
            status: 'SYNCED',
        },
    },
}

const MOCK_IMPORT_SUCCESS = {
    pieces: {
        data: {
            local: {
                hash: 'abc123',
                size: 1024,
                last_modified: new Date().toISOString(),
            },
            remote: {
                hash: 'abc123',
                size: 1024,
                last_modified: new Date().toISOString(),
            },
            last_update: new Date().toISOString(),
            has_local_changes: false,
            status: 'SYNCED',
        },
    },
}

export async function setupCloudMocks(page: Page, options: CloudMockOptions) {
    if (options.supabaseAuth === 'success') {
        await page.route(SUPABASE_URL_PATTERN, (route) => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(MOCK_SUPABASE_SESSION),
            })
        })
    } else if (options.supabaseAuth === 'invalid_credentials') {
        await page.route(SUPABASE_URL_PATTERN, (route) => {
            route.fulfill({
                status: 400,
                contentType: 'application/json',
                body: JSON.stringify({
                    error: 'invalid_grant',
                    error_description: 'Invalid login credentials',
                }),
            })
        })
    }

    if (options.backups === 'with_data') {
        await page.route('**/api/v1/cloud/backup', (route) => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(MOCK_BACKUPS_WITH_DATA),
            })
        })
    } else if (options.backups === 'empty') {
        await page.route('**/api/v1/cloud/backup', (route) => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(MOCK_BACKUPS_EMPTY),
            })
        })
    }

    if (options.cloudAuth === 'success') {
        await page.route('**/api/v1/cloud/auth', (route) => {
            if (route.request().method() === 'POST') {
                route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        role: 'owner',
                        permissions: ['read', 'write'],
                    }),
                })
            } else {
                route.fallback()
            }
        })
    }

    if (options.import === 'success') {
        await page.route('**/api/v1/cloud/backup/import', (route) => {
            route.fulfill({
                status: 200,
                contentType: 'application/json',
                body: JSON.stringify(MOCK_IMPORT_SUCCESS),
            })
        })
    } else if (options.import === 'invalid_credentials') {
        await page.route('**/api/v1/cloud/backup/import', (route) => {
            route.fulfill({
                status: 401,
                contentType: 'application/json',
                body: JSON.stringify({
                    code: 'INVALID_BACKUP_CREDENTIALS',
                }),
            })
        })
    } else if (options.import === 'invalid_then_success') {
        let importCallCount = 0
        await page.route('**/api/v1/cloud/backup/import', (route) => {
            importCallCount++
            if (importCallCount === 1) {
                route.fulfill({
                    status: 401,
                    contentType: 'application/json',
                    body: JSON.stringify({
                        code: 'INVALID_BACKUP_CREDENTIALS',
                    }),
                })
            } else {
                route.fulfill({
                    status: 200,
                    contentType: 'application/json',
                    body: JSON.stringify(MOCK_IMPORT_SUCCESS),
                })
            }
        })
    }
}

export async function clearCloudMocks(page: Page) {
    await page.unrouteAll({ behavior: 'wait' })
}
