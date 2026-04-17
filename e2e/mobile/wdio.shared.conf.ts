import type { Options } from '@wdio/types'

export const sharedConfig: Partial<Options.Testrunner> = {
    runner: 'local',
    specs: ['./test/specs/**/*.spec.ts'],
    maxInstances: 1,
    logLevel: 'info',
    outputDir: './wdio-logs',
    bail: 0,
    waitforTimeout: 30_000,
    connectionRetryTimeout: 180_000,
    connectionRetryCount: 3,
    framework: 'mocha',
    mochaOpts: {
        ui: 'bdd',
        timeout: 120_000,
    },
    reporters: ['spec'],
}
