// swift-tools-version: 5.9
import PackageDescription

// DO NOT MODIFY THIS FILE - managed by Capacitor CLI commands
let package = Package(
    name: "CapApp-SPM",
    platforms: [.iOS(.v15)],
    products: [
        .library(
            name: "CapApp-SPM",
            targets: ["CapApp-SPM"])
    ],
    dependencies: [
        .package(url: "https://github.com/ionic-team/capacitor-swift-pm.git", exact: "8.3.0"),
        .package(name: "CapacitorCommunitySqlite", path: "../../../node_modules/.pnpm/@capacitor-community+sqlite@8.1.0_@capacitor+core@8.3.0/node_modules/@capacitor-community/sqlite"),
        .package(name: "CapacitorDevice", path: "../../../node_modules/.pnpm/@capacitor+device@8.0.1_@capacitor+core@8.3.0/node_modules/@capacitor/device"),
        .package(name: "CapacitorFilesystem", path: "../../../node_modules/.pnpm/@capacitor+filesystem@8.1.2_@capacitor+core@8.3.0/node_modules/@capacitor/filesystem"),
        .package(name: "CapacitorPreferences", path: "../../../node_modules/.pnpm/@capacitor+preferences@8.0.1_@capacitor+core@8.3.0/node_modules/@capacitor/preferences"),
        .package(name: "CapacitorShare", path: "../../../node_modules/.pnpm/@capacitor+share@8.0.1_@capacitor+core@8.3.0/node_modules/@capacitor/share"),
        .package(name: "CapacitorSplashScreen", path: "../../../node_modules/.pnpm/@capacitor+splash-screen@8.0.1_@capacitor+core@8.3.0/node_modules/@capacitor/splash-screen"),
        .package(name: "CapgoCapacitorNativeBiometric", path: "../../../node_modules/.pnpm/@capgo+capacitor-native-biometric@8.4.2_@capacitor+core@8.3.0/node_modules/@capgo/capacitor-native-biometric"),
        .package(name: "CapgoCapacitorSocialLogin", path: "../../../node_modules/.pnpm/@capgo+capacitor-social-login@8.3.9_@capacitor+core@8.3.0/node_modules/@capgo/capacitor-social-login"),
        .package(name: "CapacitorPluginSafeArea", path: "../../../node_modules/.pnpm/capacitor-plugin-safe-area@5.0.0_@capacitor+core@8.3.0/node_modules/capacitor-plugin-safe-area")
    ],
    targets: [
        .target(
            name: "CapApp-SPM",
            dependencies: [
                .product(name: "Capacitor", package: "capacitor-swift-pm"),
                .product(name: "Cordova", package: "capacitor-swift-pm"),
                .product(name: "CapacitorCommunitySqlite", package: "CapacitorCommunitySqlite"),
                .product(name: "CapacitorDevice", package: "CapacitorDevice"),
                .product(name: "CapacitorFilesystem", package: "CapacitorFilesystem"),
                .product(name: "CapacitorPreferences", package: "CapacitorPreferences"),
                .product(name: "CapacitorShare", package: "CapacitorShare"),
                .product(name: "CapacitorSplashScreen", package: "CapacitorSplashScreen"),
                .product(name: "CapgoCapacitorNativeBiometric", package: "CapgoCapacitorNativeBiometric"),
                .product(name: "CapgoCapacitorSocialLogin", package: "CapgoCapacitorSocialLogin"),
                .product(name: "CapacitorPluginSafeArea", package: "CapacitorPluginSafeArea")
            ]
        )
    ]
)
