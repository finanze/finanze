import fs from "fs"
import os from "os"
import path from "path"
import { spawnSync } from "child_process"
import { fileURLToPath } from "url"
import https from "https"
import process from "node:process"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const PYODIDE_VERSION = "0.29.1"
const TARBALL_URL = `https://github.com/pyodide/pyodide/releases/download/${PYODIDE_VERSION}/pyodide-${PYODIDE_VERSION}.tar.bz2`

const DIST_PYODIDE_DIR = path.resolve(__dirname, "../dist-pyodide")
const DEST_DIR = path.join(DIST_PYODIDE_DIR, "pyodide")
const PYODIDE_REQUIREMENTS_PATH = path.resolve(
  __dirname,
  "../requirements-pyodide.txt",
)

const SYNC_MODE = (
  process.env.FINANZE_PYODIDE_SYNC_MODE ?? "minimal"
).toLowerCase()
const MINIMAL_MODE = SYNC_MODE !== "full"

const ALWAYS_INCLUDE_PACKAGES = ["micropip", "packaging", "pyparsing"]

const ESSENTIAL_RUNTIME_FILES = [
  "pyodide-lock.json",
  "pyodide.mjs",
  "pyodide.asm.wasm",
  "python_stdlib.zip",
  "pyodide.asm.js",
  "pyodide.js",
  "package.json",
  "pyodide.d.ts",
  "ffi.d.ts",
]

function downloadFile(url, destinationPath) {
  return new Promise((resolve, reject) => {
    const file = fs.createWriteStream(destinationPath)

    const request = https.get(url, res => {
      if (
        res.statusCode &&
        res.statusCode >= 300 &&
        res.statusCode < 400 &&
        res.headers.location
      ) {
        file.close()
        fs.rmSync(destinationPath, { force: true })
        downloadFile(res.headers.location, destinationPath)
          .then(resolve)
          .catch(reject)
        return
      }

      if (!res.statusCode || res.statusCode < 200 || res.statusCode >= 300) {
        file.close()
        fs.rmSync(destinationPath, { force: true })
        reject(
          new Error(
            `Failed to download ${url}: ${res.statusCode ?? "unknown"} ${res.statusMessage ?? ""}`,
          ),
        )
        return
      }

      res.pipe(file)
      file.on("finish", () => file.close(resolve))
    })

    request.on("error", err => {
      file.close()
      fs.rmSync(destinationPath, { force: true })
      reject(err)
    })

    file.on("error", err => {
      file.close()
      fs.rmSync(destinationPath, { force: true })
      reject(err)
    })
  })
}

function assertFileExists(filePath) {
  if (!fs.existsSync(filePath)) {
    throw new Error(`Missing expected Pyodide asset: ${filePath}`)
  }
}

function extractRequirementName(spec) {
  if (!spec) return null
  const trimmed = String(spec).trim()
  const match = trimmed.match(/^([A-Za-z0-9][A-Za-z0-9._-]*)/)
  return match?.[1] ? match[1] : null
}

function readPyodidePackagesFromRequirementsFile() {
  if (!fs.existsSync(PYODIDE_REQUIREMENTS_PATH)) {
    throw new Error(`Cannot find ${PYODIDE_REQUIREMENTS_PATH}.`)
  }

  const lines = fs
    .readFileSync(PYODIDE_REQUIREMENTS_PATH, "utf8")
    .split("\n")
    .map(l => l.trim())
    .filter(l => l.length > 0 && !l.startsWith("#"))

  return lines.map(extractRequirementName).filter(Boolean)
}

function ensurePythonWheelsSynced() {
  const result = spawnSync(
    "node",
    [path.resolve(__dirname, "./sync-python-wheels.mjs")],
    { stdio: "inherit" },
  )
  if (result.status !== 0) {
    throw new Error(
      `Failed to sync python wheels (exit code: ${result.status ?? "unknown"}).`,
    )
  }
}

function loadPyodideLock(pyodideSourceDir) {
  const lockPath = path.join(pyodideSourceDir, "pyodide-lock.json")
  assertFileExists(lockPath)
  return JSON.parse(fs.readFileSync(lockPath, "utf8"))
}

function resolvePackageClosure(lock, roots) {
  const packages = lock?.packages ?? {}
  const closure = new Set()
  const queue = [...roots]

  function resolveKey(name) {
    if (!name) return null
    const candidates = [
      name,
      name.toLowerCase(),
      name.replace(/_/g, "-"),
      name.replace(/_/g, "-").toLowerCase(),
      name.replace(/-/g, "_"),
      name.replace(/-/g, "_").toLowerCase(),
    ]

    for (const candidate of candidates) {
      if (candidate in packages) return candidate
    }
    return null
  }

  while (queue.length > 0) {
    const name = queue.pop()
    if (!name) continue

    const key = resolveKey(name)
    if (!key) {
      throw new Error(
        `Pyodide lockfile does not contain package '${name}'. Check FINANZE_PYODIDE_SYNC_MODE or requirements-pyodide.txt.`,
      )
    }

    if (closure.has(key)) continue

    const pkg = packages[key]

    closure.add(key)
    for (const dep of pkg.depends ?? []) {
      queue.push(dep)
    }
  }

  return closure
}

// We intentionally do NOT infer extra Pyodide packages from local wheel METADATA.
// Local wheels are installed with deps=False at runtime; anything needed should be
// explicit in requirements-pyodide.txt or requirements.txt.

function ensureDirForFile(filePath) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true })
}

function copyFileIfExists(srcPath, dstPath) {
  if (!fs.existsSync(srcPath)) return false
  ensureDirForFile(dstPath)
  fs.copyFileSync(srcPath, dstPath)
  return true
}

function copySelectedFiles(srcDir, dstDir, relativeFilePaths) {
  for (const rel of relativeFilePaths) {
    const srcPath = path.join(srcDir, rel)
    const dstPath = path.join(dstDir, rel)
    if (!fs.existsSync(srcPath)) {
      continue
    }
    copyFileIfExists(srcPath, dstPath)
  }
}

async function main() {
  console.log(
    `[Pyodide] Syncing Pyodide ${PYODIDE_VERSION} to ${DEST_DIR} (${MINIMAL_MODE ? "minimal" : "full"})...`,
  )

  // Ensure offline wheels + wheels_manifest.py exist before producing the minimal Pyodide subset.
  ensurePythonWheelsSynced()

  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), "finanze-pyodide-"))
  const tarPath = path.join(tempDir, `pyodide-${PYODIDE_VERSION}.tar.bz2`)
  const extractDir = path.join(tempDir, "extract")

  try {
    await downloadFile(TARBALL_URL, tarPath)

    fs.mkdirSync(extractDir, { recursive: true })

    const result = spawnSync("tar", ["-xjf", tarPath, "-C", extractDir], {
      stdio: "inherit",
    })

    if (result.status !== 0) {
      throw new Error(
        `Failed to extract Pyodide tarball (exit code: ${result.status ?? "unknown"}).`,
      )
    }

    const extractedPyodideDir = path.join(extractDir, "pyodide")
    assertFileExists(extractedPyodideDir)

    if (fs.existsSync(DEST_DIR)) {
      fs.rmSync(DEST_DIR, { recursive: true, force: true })
    }
    fs.mkdirSync(DEST_DIR, { recursive: true })

    if (!MINIMAL_MODE) {
      const fullCopy = spawnSync(
        "tar",
        ["-xjf", tarPath, "-C", DEST_DIR, "--strip-components=1", "pyodide"],
        { stdio: "inherit" },
      )
      if (fullCopy.status !== 0) {
        throw new Error(
          `Failed to extract Pyodide tarball into destination (exit code: ${fullCopy.status ?? "unknown"}).`,
        )
      }
    } else {
      const lock = loadPyodideLock(extractedPyodideDir)
      const mobilePackages = readPyodidePackagesFromRequirementsFile()
      const rootPackages = [
        ...new Set([...mobilePackages, ...ALWAYS_INCLUDE_PACKAGES]),
      ]

      const closure = resolvePackageClosure(lock, rootPackages)
      const fileNamesToCopy = new Set(ESSENTIAL_RUNTIME_FILES)

      for (const name of closure) {
        const pkg = lock.packages[name]
        if (!pkg?.file_name) continue
        fileNamesToCopy.add(pkg.file_name)

        const metadataName = `${pkg.file_name}.metadata`
        if (fs.existsSync(path.join(extractedPyodideDir, metadataName))) {
          fileNamesToCopy.add(metadataName)
        }
      }

      // Some runtime tools expect these to exist when present
      if (fs.existsSync(path.join(extractedPyodideDir, "repodata.json"))) {
        fileNamesToCopy.add("repodata.json")
      }

      copySelectedFiles(
        extractedPyodideDir,
        DEST_DIR,
        Array.from(fileNamesToCopy),
      )
    }

    // Always verify core runtime bits exist at the destination
    for (const rel of [
      "pyodide-lock.json",
      "pyodide.mjs",
      "pyodide.asm.wasm",
      "python_stdlib.zip",
    ]) {
      assertFileExists(path.join(DEST_DIR, rel))
    }

    console.log("[Pyodide] Sync complete.")
    console.log(
      "[Pyodide] Assets generated under dist-pyodide/pyodide (dev server serves them at /pyodide/, and build:python copies them into dist/pyodide).",
    )
    if (MINIMAL_MODE) {
      console.log(
        `[Pyodide] Minimal package set derived from ${path.relative(process.cwd(), PYODIDE_REQUIREMENTS_PATH)} (plus ${ALWAYS_INCLUDE_PACKAGES.join(", ")}).`,
      )
      console.log(
        "[Pyodide] To force a full sync, set FINANZE_PYODIDE_SYNC_MODE=full.",
      )
    }
  } finally {
    fs.rmSync(tempDir, { recursive: true, force: true })
  }
}

main().catch(err => {
  console.error("[Pyodide] Sync failed:", err)
  throw err
})
