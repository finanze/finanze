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
        'debug',
        'app-debug.apk',
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
            platformName: 'Android',
            'appium:automationName': 'UiAutomator2',
            'appium:deviceName':
                process.env.ANDROID_DEVICE_NAME || 'emulator-5554',
            'appium:udid': process.env.ANDROID_UDID || 'emulator-5554',
            'appium:app': APP_PATH,
            'appium:fullReset': true,
            'appium:noReset': false,
            'appium:chromedriverAutodownload': true,
            'appium:autoWebview': false,
            'appium:disableWindowAnimation': false,
            'appium:suppressKillServer': true,
            'appium:newCommandTimeout': 120,
        } as WebdriverIO.Capabilities,
    ],
} as Options.Testrunner
