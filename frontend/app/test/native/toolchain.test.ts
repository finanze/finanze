// @vitest-environment node
import { spawnSync } from "node:child_process"
import {
  copyFileSync,
  existsSync,
  mkdirSync,
  mkdtempSync,
  rmSync,
  writeFileSync,
} from "node:fs"
import { tmpdir } from "node:os"
import { dirname, join } from "node:path"
import { fileURLToPath } from "node:url"
import { afterEach, beforeEach, describe, expect, it } from "vitest"

const buildScript = fileURLToPath(
  new URL("../../native/tlsclient/build.sh", import.meta.url),
)

describe("mobile native toolchain setup", () => {
  let root: string
  let home: string
  let bin: string
  let script: string
  let sdk: string
  let jdk: string
  let env: NodeJS.ProcessEnv

  function executable(path: string, body = "exit 0") {
    mkdirSync(dirname(path), { recursive: true })
    writeFileSync(path, `#!/bin/bash\nset -eu\n${body}\n`, { mode: 0o755 })
  }

  function installNdk(path: string) {
    mkdirSync(join(path, "toolchains/llvm/prebuilt"), { recursive: true })
    writeFileSync(join(path, "source.properties"), "Pkg.Desc = Android NDK\n")
    return path
  }

  function run(platform = "android") {
    const result = spawnSync("/bin/bash", [script, "--platform", platform], {
      env,
      encoding: "utf8",
    })
    if (result.error) throw result.error
    return {
      status: result.status,
      output: result.stdout + result.stderr,
    }
  }

  beforeEach(() => {
    root = mkdtempSync(join(tmpdir(), "finanze-toolchain-"))
    home = join(root, "home with spaces")
    bin = join(root, "bin")
    script = join(root, "native", "build.sh")
    sdk = join(home, "Library/Android/sdk")
    jdk = join(root, "jdk with spaces")
    mkdirSync(dirname(script), { recursive: true })
    mkdirSync(home, { recursive: true })
    copyFileSync(buildScript, script)
    executable(join(bin, "uname"), 'printf "Darwin\\n"')
    executable(
      join(bin, "go"),
      `if [[ "$1" == "env" ]]; then
  printf '%s\\n' "$HOME/go"
else
  printf 'Reached iOS compiler: %s\\n' "\${DEVELOPER_DIR:-}" >&2
  exit 42
fi`,
    )
    executable(
      join(bin, "gomobile"),
      `printf 'Bound with SDK=%s NDK=%s JAVA_HOME=%s\\n' "$ANDROID_HOME" "$ANDROID_NDK_HOME" "\${JAVA_HOME:-}"
printf 'Arguments: %s\\n' "$*"
while [[ $# -gt 0 ]]; do
  if [[ "$1" == "-o" ]]; then touch "$2"; break; fi
  shift
done`,
    )
    for (const tool of ["java", "javac", "jar"]) {
      executable(join(jdk, "bin", tool))
    }
    env = {
      HOME: home,
      PATH: `${bin}:/usr/bin:/bin`,
      JAVA_HOME: jdk,
    }
  })

  afterEach(() => {
    rmSync(root, { recursive: true, force: true })
  })

  it("detects the newest NDK numerically and exports it to gomobile", () => {
    for (const version of ["9.0.123", "28.9.999", "29.0.999", "29.0.1000"]) {
      installNdk(join(sdk, "ndk", version))
    }
    mkdirSync(join(sdk, "ndk", "30.0.1000"), { recursive: true })
    installNdk(join(sdk, "ndk", "invalid"))

    const result = run()

    expect(result.status).toBe(0)
    expect(result.output).toContain(
      `Bound with SDK=${sdk} NDK=${join(sdk, "ndk", "29.0.1000")} JAVA_HOME=${jdk}`,
    )
    expect(result.output).toContain("-target=android/arm64 -androidapi 24")
    expect(existsSync(join(dirname(script), "build/tlsclient.aar"))).toBe(true)
  })

  it.each(["ANDROID_HOME", "ANDROID_SDK_ROOT"])(
    "discovers the NDK from %s",
    variable => {
      const customSdk = join(root, "custom sdk")
      env[variable] = customSdk
      installNdk(join(customSdk, "ndk", "28.0.13004108"))

      const result = run()

      expect(result.status).toBe(0)
      expect(result.output).toContain(`Bound with SDK=${customSdk}`)
    },
  )

  it("prefers ANDROID_HOME over ANDROID_SDK_ROOT", () => {
    env.ANDROID_HOME = sdk
    env.ANDROID_SDK_ROOT = join(root, "other sdk")
    installNdk(join(sdk, "ndk", "28.0.13004108"))

    expect(run().output).toContain(`Bound with SDK=${sdk}`)
  })

  it("detects the default Linux SDK location", () => {
    executable(join(bin, "uname"), 'printf "Linux\\n"')
    const linuxSdk = join(home, "Android/Sdk")
    installNdk(join(linuxSdk, "ndk", "28.0.13004108"))

    const result = run()

    expect(result.status).toBe(0)
    expect(result.output).toContain(`Bound with SDK=${linuxSdk}`)
  })

  it.each(["ANDROID_NDK_HOME", "ANDROID_NDK_ROOT"])(
    "honors an explicit %s outside the SDK",
    variable => {
      const customNdk = installNdk(join(root, "custom ndk"))
      env[variable] = customNdk
      installNdk(join(sdk, "ndk", "29.0.14206865"))

      const result = run()

      expect(result.status).toBe(0)
      expect(result.output).toContain(`NDK=${customNdk}`)
    },
  )

  it("prefers ANDROID_NDK_HOME over ANDROID_NDK_ROOT", () => {
    env.ANDROID_NDK_HOME = installNdk(join(root, "selected ndk"))
    env.ANDROID_NDK_ROOT = join(root, "invalid ndk")

    expect(run().output).toContain(`NDK=${env.ANDROID_NDK_HOME}`)
  })

  it("does not fall back when an explicit NDK is invalid", () => {
    env.ANDROID_NDK_HOME = join(root, "missing ndk")
    installNdk(join(sdk, "ndk", "29.0.14206865"))

    const result = run()

    expect(result.status).toBe(1)
    expect(result.output).toContain("ERROR: No valid Android NDK found")
    expect(result.output).not.toContain("Bound with")
  })

  it("explains missing NDK setup and preserves existing builds", () => {
    const previousBuild = join(dirname(script), "build", "previous.aar")
    mkdirSync(dirname(previousBuild), { recursive: true })
    writeFileSync(previousBuild, "previous build")

    const result = run()

    expect(result.status).toBe(1)
    expect(result.output).toContain("NDK (Side by side)")
    expect(result.output).toContain("export ANDROID_NDK_HOME=")
    expect(existsSync(previousBuild)).toBe(true)
  })

  it("warns about JAVA_HOME but allows a working JDK on PATH", () => {
    delete env.JAVA_HOME
    env.PATH = `${jdk}/bin:${env.PATH}`
    installNdk(join(sdk, "ndk", "28.0.13004108"))

    const result = run()

    expect(result.status).toBe(0)
    expect(result.output).toContain("WARNING: JAVA_HOME is not set")
    expect(result.output).toContain("/usr/libexec/java_home -v 21")
  })

  it("rejects an invalid JAVA_HOME even when PATH has Java", () => {
    env.JAVA_HOME = join(root, "missing jdk")
    env.PATH = `${jdk}/bin:${env.PATH}`
    installNdk(join(sdk, "ndk", "28.0.13004108"))

    const result = run()

    expect(result.status).toBe(1)
    expect(result.output).toContain("is not a valid JDK")
    expect(result.output).not.toContain("Bound with")
  })

  it("rejects non-working Java launchers and explains JDK setup", () => {
    installNdk(join(sdk, "ndk", "28.0.13004108"))
    executable(join(jdk, "bin", "java"), "exit 1")

    const result = run()

    expect(result.status).toBe(1)
    expect(result.output).toContain("A working JDK is required")
    expect(result.output).toContain("set JAVA_HOME")
  })

  it("reports a missing gomobile before starting the build", () => {
    installNdk(join(sdk, "ndk", "28.0.13004108"))
    rmSync(join(bin, "gomobile"))

    const result = run()

    expect(result.status).toBe(1)
    expect(result.output).toContain("ERROR: gomobile not found")
  })

  it("explains DEVELOPER_DIR when only Command Line Tools are selected", () => {
    executable(join(bin, "xcrun"), "exit 1")

    const result = run("ios")

    expect(result.status).toBe(1)
    expect(result.output).toContain("Command Line Tools alone are not enough")
    expect(result.output).toContain(
      'export DEVELOPER_DIR="/Applications/Xcode.app/Contents/Developer"',
    )
  })

  it("reports missing simulator SDKs before compiling", () => {
    executable(
      join(bin, "xcrun"),
      'if [[ "$2" == "iphonesimulator" ]]; then exit 1; fi\nprintf "/mock/sdk\\n"',
    )

    const result = run("ios")

    expect(result.status).toBe(1)
    expect(result.output).toContain("iOS and simulator SDKs")
    expect(result.output).not.toContain("Reached iOS compiler")
  })

  it("preserves an explicit DEVELOPER_DIR and does not require Android for iOS", () => {
    env.DEVELOPER_DIR = "/Applications/Custom Xcode.app/Contents/Developer"
    delete env.JAVA_HOME
    executable(join(bin, "xcrun"), 'printf "/mock/sdk\\n"')

    const result = run("ios")

    expect(result.status).toBe(42)
    expect(result.output).toContain(
      `Reached iOS compiler: ${env.DEVELOPER_DIR}`,
    )
    expect(result.output).not.toContain("Android NDK")
    expect(result.output).not.toContain("JAVA_HOME")
  })

  it("checks Android before compiling when both platforms are requested", () => {
    executable(join(bin, "xcrun"), 'printf "/mock/sdk\\n"')

    const result = run("all")

    expect(result.status).toBe(1)
    expect(result.output).toContain("ERROR: No valid Android NDK found")
    expect(result.output).not.toContain("Reached iOS compiler")
  })
})
