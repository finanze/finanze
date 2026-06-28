import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import { sharedConfig } from './wdio.shared.conf.js'

const __dirname = dirname(fileURLToPath(import.meta.url))

function getSimulatorRuntimeVersion(): string {
    try {
        const out = execSync('xcrun simctl list runtimes --json', {
            encoding: 'utf-8',
        })
        const data = JSON.parse(out) as {
            runtimes: Array<{
                identifier: string
                version: string
                isAvailable?: boolean
                platform?: string
            }>
        }
        const versions = data.runtimes
            .filter(
                (r) =>
                    r.isAvailable !== false &&
                    (r.platform === 'iOS' || r.identifier.includes('iOS')),
            )
            .map((r) => r.version)
            .filter(Boolean)
            .sort((a, b) => b.localeCompare(a, undefined, { numeric: true }))
        if (versions.length > 0) {
            return versions[0]
        }
    } catch {}
    return '18.0'
}

function findWDADerivedDataPath(): string | undefined {
    try {
        const wdaProject = execSync(
            "find node_modules -path '*/appium-webdriveragent/WebDriverAgent.xcodeproj' -print -quit",
            { encoding: 'utf-8', cwd: __dirname },
        ).trim()
        if (wdaProject) {
            return join(__dirname, dirname(dirname(wdaProject)))
        }
    } catch {}
    return undefined
}

const APP_PATH =
    process.env.IOS_APP_PATH ||
    join(
        __dirname,
        '..',
        '..',
        'frontend',
        'app',
        'ios',
        'App',
        'build',
        'ios',
        'Build',
        'Products',
        'Debug-iphonesimulator',
        'App.app',
    )

export const config: WebdriverIO.Config = {
    ...sharedConfig,
    specFileRetries: 2,
    connectionRetryTimeout: 600_000,
    services: [
        [
            'appium',
            {
                args: {
                    relaxedSecurity: true,
                },
                appiumStartTimeout: 120_000,
            },
        ],
    ],
    capabilities: [
        {
            platformName: 'iOS',
            'appium:automationName': 'XCUITest',
            'appium:deviceName': process.env.IOS_DEVICE_NAME || 'iPhone 17 Pro',
            'appium:platformVersion':
                process.env.IOS_PLATFORM_VERSION ||
                getSimulatorRuntimeVersion(),
            ...(process.env.IOS_DEVICE_UDID
                ? { 'appium:udid': process.env.IOS_DEVICE_UDID }
                : {}),
            'appium:app': APP_PATH,
            'appium:fullReset': false,
            'appium:noReset': false,
            'appium:usePrebuiltWDA': !!process.env.CI,
            ...(process.env.CI
                ? { 'appium:derivedDataPath': findWDADerivedDataPath() }
                : {}),
            'appium:showXcodeLog': !!process.env.CI,
            'appium:webviewConnectTimeout': 30_000,
            'appium:includeSafariInWebviews': false,
            'appium:wdaLaunchTimeout': 300_000,
            'appium:simulatorStartupTimeout': 180_000,
            'appium:newCommandTimeout': 120,
        } as WebdriverIO.Capabilities,
    ],
} satisfies WebdriverIO.Config
