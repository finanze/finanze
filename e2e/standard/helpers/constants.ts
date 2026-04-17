export const BACKEND_PORT = Number(process.env.E2E_BACKEND_PORT || 7692)
export const BACKEND_URL = `http://localhost:${BACKEND_PORT}`

export const TEST_USER = 'testuser'
export const TEST_PASSWORD = 'TestPassword123!'
export const TEST_NEW_PASSWORD = 'NewPassword456!'

export const URBANITAE_ID = 'e0000000-0000-0000-0000-000000000004'
export const WECITY_ID = 'e0000000-0000-0000-0000-000000000005'
export const TRADE_REPUBLIC_ID = 'e0000000-0000-0000-0000-000000000003'
export const UNICAJA_ID = 'e0000000-0000-0000-0000-000000000002'
export const ING_ID = 'e0000000-0000-0000-0000-000000000010'
export const BINANCE_ID = 'ce000000-0000-0000-0000-000000000001'

export const MOCK_PIN_CODE = '123456'

export const BINANCE_CREDENTIALS = {
    apiKey: 'mock-api-key',
    secretKey: 'mock-secret-key',
}

export const TRADE_REPUBLIC_CREDENTIALS = {
    phone: '+34612345678',
    password: '1234',
}

export const UNICAJA_CREDENTIALS = {
    user: 'test-unicaja-user',
    password: 'MockPassword123',
}
