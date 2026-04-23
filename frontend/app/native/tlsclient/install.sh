#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_DIR="$SCRIPT_DIR/build"
IOS_DEST="$SCRIPT_DIR/../../ios/App"
ANDROID_DEST="$SCRIPT_DIR/../../android/app/libs"

# iOS
if [ -d "$BUILD_DIR/Tlsclient.xcframework" ]; then
    echo "=== Installing iOS xcframework ==="
    rm -rf "$IOS_DEST/Tlsclient.xcframework"
    cp -R "$BUILD_DIR/Tlsclient.xcframework" "$IOS_DEST/"
    echo "  Copied to $IOS_DEST/Tlsclient.xcframework"
else
    echo "  SKIP iOS: $BUILD_DIR/Tlsclient.xcframework not found (run build.sh first)"
fi

# Android
if [ -f "$BUILD_DIR/tlsclient.aar" ]; then
    echo "=== Installing Android AAR ==="
    mkdir -p "$ANDROID_DEST"
    cp "$BUILD_DIR/tlsclient.aar" "$ANDROID_DEST/"
    echo "  Copied to $ANDROID_DEST/tlsclient.aar"
else
    echo "  SKIP Android: $BUILD_DIR/tlsclient.aar not found (run build.sh first)"
fi

echo ""
echo "Done!"
