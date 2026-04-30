#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
FRONTEND_APP="$SCRIPT_DIR/../../frontend/app"
ANDROID_SDK="${ANDROID_HOME:-$HOME/Library/Android/sdk}"

IOS_APP_PATH="${IOS_APP_PATH:-$(find "$HOME/Library/Developer/Xcode/DerivedData" \
  -path "*/Debug-iphonesimulator/App.app/Info.plist" -type f 2>/dev/null \
  | xargs ls -t 2>/dev/null | head -1 | sed 's|/Info.plist$||' || echo "")}"

ANDROID_APP_PATH="${ANDROID_APP_PATH:-$FRONTEND_APP/android/app/build/outputs/apk/full/debug/app-full-debug.apk}"

usage() {
  echo "Usage: $0 <ios|android|both>"
  echo ""
  echo "Runs mobile e2e tests locally."
  echo "Automatically boots simulators/emulators if needed."
  echo ""
  echo "Environment variables:"
  echo "  IOS_APP_PATH         Override iOS .app path (auto-detected from Xcode DerivedData)"
  echo "  ANDROID_APP_PATH     Override Android .apk path (default: frontend/app/android/...)"
  echo "  IOS_DEVICE_NAME      Simulator device (default: iPhone 17 Pro)"
  echo "  ANDROID_DEVICE_NAME  Emulator device name (default: emulator-5554)"
  echo "  ANDROID_AVD          AVD name for emulator (auto-detected if not set)"
  echo "  ANDROID_UDID         Emulator UDID (default: emulator-5554)"
  exit 1
}

ensure_drivers() {
  local installed
  installed=$(cd "$SCRIPT_DIR" && pnpm exec appium driver list --installed 2>&1)

  if [[ "$1" == "ios" || "$1" == "both" ]]; then
    if ! echo "$installed" | grep -q "xcuitest"; then
      echo "Installing Appium XCUITest driver..."
      (cd "$SCRIPT_DIR" && pnpm exec appium driver install xcuitest)
    fi
  fi

  if [[ "$1" == "android" || "$1" == "both" ]]; then
    if ! echo "$installed" | grep -q "uiautomator2"; then
      echo "Installing Appium UiAutomator2 driver..."
      (cd "$SCRIPT_DIR" && pnpm exec appium driver install uiautomator2)
    fi
  fi
}

ensure_ios_simulator() {
  local device_name="${IOS_DEVICE_NAME:-iPhone 17 Pro}"
  local booted
  booted=$(xcrun simctl list devices booted 2>/dev/null | grep "$device_name" || true)

  if [[ -n "$booted" ]]; then
    echo "iOS Simulator '$device_name' is already booted."
    return
  fi

  local device_id
  device_id=$(xcrun simctl list devices available 2>/dev/null \
    | grep "$device_name" | head -1 | grep -oE '[0-9A-F-]{36}' || true)

  if [[ -z "$device_id" ]]; then
    echo "Error: No available simulator matching '$device_name'."
    echo "Available simulators:"
    xcrun simctl list devices available | grep "iPhone"
    exit 1
  fi

  echo "Booting iOS Simulator '$device_name' ($device_id)..."
  xcrun simctl boot "$device_id" 2>/dev/null || true
  echo "Simulator booted."
}

ensure_android_emulator() {
  local udid="${ANDROID_UDID:-emulator-5554}"

  if adb -s "$udid" shell getprop sys.boot_completed 2>/dev/null | grep -q "1"; then
    echo "Android emulator '$udid' is already running."
    return
  fi

  local avd="${ANDROID_AVD:-}"
  if [[ -z "$avd" ]]; then
    avd=$("$ANDROID_SDK/emulator/emulator" -list-avds 2>/dev/null | head -1 || true)
  fi

  if [[ -z "$avd" ]]; then
    echo "Error: No Android AVD found. Create one in Android Studio or set ANDROID_AVD."
    exit 1
  fi

  echo "Starting Android emulator '$avd'..."
  "$ANDROID_SDK/emulator/emulator" -avd "$avd" -no-audio -no-boot-anim &
  local emu_pid=$!

  echo "Waiting for emulator to boot..."
  local waited=0
  while [[ $waited -lt 120 ]]; do
    if adb -s "$udid" shell getprop sys.boot_completed 2>/dev/null | grep -q "1"; then
      echo "Emulator ready."
      return
    fi
    sleep 2
    waited=$((waited + 2))
  done

  echo "Error: Emulator did not boot within 120s."
  kill "$emu_pid" 2>/dev/null || true
  exit 1
}

run_ios() {
  if [[ -z "$IOS_APP_PATH" || ! -d "$IOS_APP_PATH" ]]; then
    echo "Error: iOS app not found."
    echo "Build it from Xcode or set IOS_APP_PATH."
    echo "  Looked at: $IOS_APP_PATH"
    exit 1
  fi

  ensure_ios_simulator

  echo "iOS app: $IOS_APP_PATH"
  echo ""
  (cd "$SCRIPT_DIR" && IOS_APP_PATH="$IOS_APP_PATH" pnpm test:ios)
}

run_android() {
  if [[ ! -f "$ANDROID_APP_PATH" ]]; then
    echo "Error: Android APK not found at $ANDROID_APP_PATH"
    echo "Build it from Android Studio or set ANDROID_APP_PATH."
    exit 1
  fi

  ensure_android_emulator

  echo "Android APK: $ANDROID_APP_PATH"
  echo ""
  (cd "$SCRIPT_DIR" && ANDROID_APP_PATH="$ANDROID_APP_PATH" pnpm test:android)
}

PLATFORM="${1:-}"
[[ -z "$PLATFORM" ]] && usage

ensure_drivers "$PLATFORM"

case "$PLATFORM" in
  ios)
    run_ios
    ;;
  android)
    run_android
    ;;
  both)
    echo "=== Running iOS tests ==="
    run_ios
    echo ""
    echo "=== Running Android tests ==="
    run_android
    ;;
  *)
    usage
    ;;
esac
