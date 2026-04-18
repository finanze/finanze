import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { execSync } from 'node:child_process'
import { sharedConfig } from './wdio.shared.conf.js'
import type { Options } from '@wdio/types'

const __dirname = dirname(fileURLToPath(import.meta.url))

function getIOSSDKVersion(): string {
    try {
        return execSync('xcodebuild -version -sdk iphonesimulator SDKVersion', {
            encoding: 'utf-8',
        }).trim()
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
                process.env.IOS_PLATFORM_VERSION || getIOSSDKVersion(),
            ...(process.env.IOS_DEVICE_UDID && {
                'appium:udid': process.env.IOS_DEVICE_UDID,
            }),
            'appium:app': APP_PATH,
            'appium:fullReset': false,
            'appium:noReset': false,
            'appium:usePrebuiltWDA': !!process.env.CI,
            'appium:showXcodeLog': !!process.env.CI,
            'appium:webviewConnectTimeout': 30_000,
            'appium:includeSafariInWebviews': false,
            'appium:wdaLaunchTimeout': 300_000,
            'appium:simulatorStartupTimeout': 180_000,
            'appium:newCommandTimeout': 120,
        } as WebdriverIO.Capabilities,
    ],
} as Options.Testrunner
