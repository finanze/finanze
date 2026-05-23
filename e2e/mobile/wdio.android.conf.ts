import { join, dirname } from 'node:path'
import { fileURLToPath } from 'node:url'
import { sharedConfig } from './wdio.shared.conf.js'
import type { Options } from '@wdio/types'

const __dirname = dirname(fileURLToPath(import.meta.url))

const APP_PATH =
    process.env.ANDROID_APP_PATH ||
    join(
        __dirname,
        '..',
        '..',
        'frontend',
        'app',
        'android',
        'app',
        'build',
        'outputs',
        'apk',
        'full',
        'debug',
        'app-full-debug.apk',
    )

export const config: Options.Testrunner = {
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
            platformName: 'Android',
            'appium:automationName': 'UiAutomator2',
            'appium:deviceName':
                process.env.ANDROID_DEVICE_NAME || 'emulator-5554',
            'appium:udid': process.env.ANDROID_UDID || 'emulator-5554',
            'appium:app': APP_PATH,
            'appium:allowTestPackages': true,
            'appium:fullReset': true,
            'appium:noReset': false,
            'appium:chromedriverAutodownload': true,
            'appium:autoWebview': false,
            'appium:disableWindowAnimation': true,
            'appium:appWaitDuration': 60_000,
            'appium:suppressKillServer': true,
            'appium:newCommandTimeout': 120,
            'appium:uiautomator2ServerLaunchTimeout': 90_000,
        } as WebdriverIO.Capabilities,
    ],
} as Options.Testrunner
