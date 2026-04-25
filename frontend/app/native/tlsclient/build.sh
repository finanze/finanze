#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Parse --platform flag (ios, android, all). Default: all
PLATFORM="all"
while [[ $# -gt 0 ]]; do
    case "$1" in
        --platform)
            PLATFORM="${2:-all}"
            shift 2
        ;;
        *)
            echo "Unknown option: $1" >&2
            exit 1
        ;;
    esac
done

export PATH="$PATH:$(go env GOPATH)/bin"
export GOFLAGS=-mod=mod

OUTPUT_DIR="$SCRIPT_DIR/build"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

build_ios() {
    MIN_IOS="15.0"
    SDKROOT_IOS=$(xcrun --sdk iphoneos --show-sdk-path)
    SDKROOT_SIM=$(xcrun --sdk iphonesimulator --show-sdk-path)
    CLANG_IOS="$(xcrun --sdk iphoneos -f clang)"
    CLANG_SIM="$(xcrun --sdk iphonesimulator -f clang)"
    
    # Step 1: Build static archives with c-archive (supported on ios)
    echo "=== Building c-archive iOS arm64 (device) ==="
    CGO_ENABLED=1 \
    GOOS=ios \
    GOARCH=arm64 \
    CC="${CLANG_IOS} -isysroot ${SDKROOT_IOS} -miphoneos-version-min=${MIN_IOS}" \
    go build -buildmode=c-archive -trimpath -ldflags="-s -w" -o "$OUTPUT_DIR/tlsclient-ios-arm64.a" .
    
    echo "=== Building c-archive iOS arm64 (simulator) ==="
    CGO_ENABLED=1 \
    GOOS=ios \
    GOARCH=arm64 \
    CGO_CFLAGS="-target arm64-apple-ios${MIN_IOS}-simulator" \
    CGO_LDFLAGS="-target arm64-apple-ios${MIN_IOS}-simulator" \
    CC="${CLANG_SIM} -isysroot ${SDKROOT_SIM}" \
    go build -buildmode=c-archive -trimpath -ldflags="-s -w" -o "$OUTPUT_DIR/tlsclient-sim-arm64.a" .
    
    # Step 2: Create dynamic frameworks from static archives
    echo "=== Creating dynamic framework (device) ==="
    mkdir -p "$OUTPUT_DIR/ios-arm64/Tlsclient.framework"
    ${CLANG_IOS} -isysroot ${SDKROOT_IOS} -miphoneos-version-min=${MIN_IOS} \
    -arch arm64 \
    -shared \
    -Wl,-all_load "$OUTPUT_DIR/tlsclient-ios-arm64.a" \
    -framework Foundation -framework Security -framework CoreFoundation \
    -lresolv \
    -install_name @rpath/Tlsclient.framework/Tlsclient \
    -o "$OUTPUT_DIR/ios-arm64/Tlsclient.framework/Tlsclient"
    
    echo "=== Creating dynamic framework (simulator) ==="
    mkdir -p "$OUTPUT_DIR/ios-sim/Tlsclient.framework"
    ${CLANG_SIM} -isysroot ${SDKROOT_SIM} \
    -target arm64-apple-ios${MIN_IOS}-simulator \
    -shared \
    -Wl,-all_load "$OUTPUT_DIR/tlsclient-sim-arm64.a" \
    -framework Foundation -framework Security -framework CoreFoundation \
    -lresolv \
    -install_name @rpath/Tlsclient.framework/Tlsclient \
    -o "$OUTPUT_DIR/ios-sim/Tlsclient.framework/Tlsclient"
    
    # Add Info.plist to both
    for dir in "$OUTPUT_DIR/ios-arm64/Tlsclient.framework" "$OUTPUT_DIR/ios-sim/Tlsclient.framework"; do
    cat > "$dir/Info.plist" << 'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleIdentifier</key><string>me.finanze.tlsclient</string>
  <key>CFBundleName</key><string>Tlsclient</string>
  <key>CFBundleExecutable</key><string>Tlsclient</string>
  <key>CFBundlePackageType</key><string>FMWK</string>
  <key>CFBundleVersion</key><string>1.0</string>
  <key>CFBundleShortVersionString</key><string>1.0</string>
  <key>MinimumOSVersion</key><string>15.0</string>
</dict>
</plist>
PLIST
    done
    
    # Step 3: Create xcframework
    echo "=== Creating xcframework ==="
    xcodebuild -create-xcframework \
    -framework "$OUTPUT_DIR/ios-arm64/Tlsclient.framework" \
    -framework "$OUTPUT_DIR/ios-sim/Tlsclient.framework" \
    -output "$OUTPUT_DIR/Tlsclient.xcframework"
    
    echo ""
    echo "=== Verifying ==="
    file "$OUTPUT_DIR/ios-arm64/Tlsclient.framework/Tlsclient"
    ls -lh "$OUTPUT_DIR/ios-arm64/Tlsclient.framework/Tlsclient"
    nm -gU "$OUTPUT_DIR/ios-arm64/Tlsclient.framework/Tlsclient" | grep -i "Tls" | head -10
    
    echo ""
    echo "iOS build complete: $OUTPUT_DIR/Tlsclient.xcframework"
}

build_android() {
    echo ""
    echo "=== Building Android AAR ==="
    ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-$HOME/Library/Android/sdk/ndk/29.0.14206865}"
    ANDROID_HOME="${ANDROID_HOME:-$HOME/Library/Android/sdk}"
    export ANDROID_NDK_HOME ANDROID_HOME
    
    if command -v gomobile &>/dev/null; then
        gomobile bind -target=android/arm64 -androidapi 24 -ldflags="-s -w" -o "$OUTPUT_DIR/tlsclient.aar" ./mobile
        echo "Android build complete: $OUTPUT_DIR/tlsclient.aar"
    else
        echo "  SKIPPED: gomobile not found (install with: go install golang.org/x/mobile/cmd/gomobile@latest)"
        exit 1
    fi
}

case "$PLATFORM" in
    ios)
        build_ios
    ;;
    android)
        build_android
    ;;
    all)
        build_ios
        build_android
    ;;
    *)
        echo "Unknown platform: $PLATFORM (use ios, android, or all)" >&2
        exit 1
    ;;
esac

echo ""
echo "Build complete!"
