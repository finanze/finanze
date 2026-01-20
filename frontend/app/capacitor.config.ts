import type { CapacitorConfig } from "@capacitor/cli"

const config: CapacitorConfig = {
  appId: "finanze.me",
  appName: "Finanze",
  webDir: "dist",
  server: {
    androidScheme: "https",
  },
  plugins: {
    CapacitorHttp: {
      enabled: true,
    },
    CapacitorSQLite: {
      iosDatabaseLocation: "Library/CapacitorDatabase",
      iosIsEncryption: true,
      iosKeychainPrefix: "finanze",
      androidIsEncryption: true,
    },
  },
}

export default config
