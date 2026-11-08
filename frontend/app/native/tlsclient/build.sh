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

case "$PLATFORM" in
    ios|android|all) ;;
    *)
        echo "Unknown platform: $PLATFORM (use ios, android, or all)" >&2
        exit 1
    ;;
esac

if ! command -v go &>/dev/null; then
    echo "ERROR: Go is required to build the mobile TLS client." >&2
    exit 1
fi
export PATH="$PATH:$(go env GOPATH)/bin"
export GOFLAGS=-mod=mod

prepare_ios() {
    if ! SDKROOT_IOS=$(xcrun --sdk iphoneos --show-sdk-path) ||
       ! SDKROOT_SIM=$(xcrun --sdk iphonesimulator --show-sdk-path) ||
       ! CLANG_IOS=$(xcrun --sdk iphoneos -f clang) ||
       ! CLANG_SIM=$(xcrun --sdk iphonesimulator -f clang); then
        echo "ERROR: Full Xcode with the iOS and simulator SDKs is required; Command Line Tools alone are not enough." >&2
        echo 'Open Xcode to finish installing its components, then set the developer directory before retrying:' >&2
        echo '  export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"' >&2
        echo 'Adjust this path for your Xcode installation, or select it globally with xcode-select --switch.' >&2
        exit 1
    fi
}

prepare_android() {
    ANDROID_HOME="${ANDROID_HOME:-${ANDROID_SDK_ROOT:-}}"
    if [[ -z "$ANDROID_HOME" ]]; then
        if [[ "$(uname -s)" == "Darwin" ]]; then
            ANDROID_HOME="$HOME/Library/Android/sdk"
        else
            ANDROID_HOME="$HOME/Android/Sdk"
        fi
    fi
    ANDROID_NDK_HOME="${ANDROID_NDK_HOME:-${ANDROID_NDK_ROOT:-}}"
    if [[ -z "$ANDROID_NDK_HOME" ]]; then
        local version candidate
        while IFS= read -r version; do
            candidate="$ANDROID_HOME/ndk/$version"
            if [[ -f "$candidate/source.properties" && -d "$candidate/toolchains/llvm/prebuilt" ]]; then
                ANDROID_NDK_HOME="$candidate"
                break
            fi
        done < <(
            for candidate in "$ANDROID_HOME"/ndk/*; do
                version="${candidate##*/}"
                if [[ "$version" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
                    printf '%s\n' "$version"
                fi
            done | sort -t . -k1,1nr -k2,2nr -k3,3nr
        )
    fi
    if [[ -z "$ANDROID_NDK_HOME" || ! -f "$ANDROID_NDK_HOME/source.properties" ||
          ! -d "$ANDROID_NDK_HOME/toolchains/llvm/prebuilt" ]]; then
        echo "ERROR: No valid Android NDK found (ANDROID_NDK_HOME='$ANDROID_NDK_HOME', SDK='$ANDROID_HOME')." >&2
        echo 'Install NDK (Side by side), r28 or newer, in Android Studio > SDK Manager > SDK Tools.' >&2
        echo 'For a custom SDK, set ANDROID_HOME; for a custom NDK, set ANDROID_NDK_HOME to its version directory:' >&2
        echo '  export ANDROID_NDK_HOME="/path/to/Android/sdk/ndk/<installed-version>"' >&2
        exit 1
    fi
    export ANDROID_HOME ANDROID_NDK_HOME
    echo "Using Android SDK: $ANDROID_HOME"
    echo "Using Android NDK: $ANDROID_NDK_HOME"

    if [[ -z "${JAVA_HOME:-}" ]]; then
        echo 'WARNING: JAVA_HOME is not set; using Java tools from PATH. Set JAVA_HOME to your JDK (21+ recommended).' >&2
        echo 'On macOS: export JAVA_HOME="$(/usr/libexec/java_home -v 21)"' >&2
    else
        if [[ ! -x "$JAVA_HOME/bin/java" || ! -x "$JAVA_HOME/bin/javac" || ! -x "$JAVA_HOME/bin/jar" ]]; then
            echo "ERROR: JAVA_HOME='$JAVA_HOME' is not a valid JDK; it must contain bin/java, bin/javac and bin/jar." >&2
            exit 1
        fi
        export PATH="$JAVA_HOME/bin:$PATH"
    fi
    if ! command -v java &>/dev/null || ! command -v javac &>/dev/null ||
       ! command -v jar &>/dev/null || ! java -version || ! javac -version; then
        echo 'ERROR: A working JDK is required. Install JDK 21+ and set JAVA_HOME to its installation directory.' >&2
        echo 'On macOS: export JAVA_HOME="$(/usr/libexec/java_home -v 21)"' >&2
        exit 1
    fi
    if ! command -v gomobile &>/dev/null; then
        echo "ERROR: gomobile not found (install with: go install golang.org/x/mobile/cmd/gomobile@latest)" >&2
        exit 1
    fi
}

case "$PLATFORM" in
    ios) prepare_ios ;;
    android) prepare_android ;;
    all)
        prepare_ios
        prepare_android
    ;;
esac

OUTPUT_DIR="$SCRIPT_DIR/build"
rm -rf "$OUTPUT_DIR"
mkdir -p "$OUTPUT_DIR"

build_ios() {
    MIN_IOS="15.0"
    
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
    gomobile bind -target=android/arm64 -androidapi 24 -ldflags="-s -w" -o "$OUTPUT_DIR/tlsclient.aar" ./mobile
    echo "Android build complete: $OUTPUT_DIR/tlsclient.aar"
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
esac

echo ""
echo "Build complete!"
