export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 7592)
export const BACKEND_URL = `http://localhost:${BACKEND_PORT}`

export const TEST_USER = 'testuser'
export const TEST_PASSWORD = 'TestPassword123!'
export const TEST_NEW_PASSWORD = 'NewPassword456!'

export const URBANITAE_ID = 'e0000000-0000-0000-0000-000000000004'
export const TRADE_REPUBLIC_ID = 'e0000000-0000-0000-0000-000000000003'
export const BINANCE_ID = 'ce000000-0000-0000-0000-000000000001'

export const MOCK_PIN_CODE = '1234'

export const BINANCE_CREDENTIALS = {
    apiKey: 'mock-api-key',
    secretKey: 'mock-secret-key',
}
