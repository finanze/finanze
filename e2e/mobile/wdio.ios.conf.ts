import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import { sharedConfig } from './wdio.shared.conf.js'
import type { Options } from '@wdio/types'

const __dirname = dirname(fileURLToPath(import.meta.url))

function getLatestIOSVersion(): string {
    try {
        const output = execSync('xcrun simctl list runtimes -j', {
            encoding: 'utf-8',
        })
        const data = JSON.parse(output)
        const iosRuntimes = data.runtimes
            .filter(
                (r: { platform: string; isAvailable: boolean }) =>
                    r.platform === 'iOS' && r.isAvailable,
            )
            .sort((a: { version: string }, b: { version: string }) =>
                b.version.localeCompare(a.version, undefined, {
                    numeric: true,
                }),
            )
        return iosRuntimes[0]?.version || '18.0'
    } catch {
        return '18.0'
    }
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

export const config: Options.Testrunner = {
    ...sharedConfig,
    services: [
        [
            'appium',
            {
                args: {
                    relaxedSecurity: true,
                },
            },
        ],
    ],
    capabilities: [
        {
            platformName: 'iOS',
            'appium:automationName': 'XCUITest',
            'appium:deviceName': process.env.IOS_DEVICE_NAME || 'iPhone 17 Pro',
            'appium:platformVersion':
                process.env.IOS_PLATFORM_VERSION || getLatestIOSVersion(),
            'appium:app': APP_PATH,
            'appium:fullReset': true,
            'appium:noReset': false,
            'appium:webviewConnectTimeout': 30_000,
            'appium:includeSafariInWebviews': false,
            'appium:wdaLaunchTimeout': 120_000,
            'appium:newCommandTimeout': 120,
        } as WebdriverIO.Capabilities,
    ],
} as Options.Testrunner
