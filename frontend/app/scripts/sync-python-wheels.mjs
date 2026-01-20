import fs from "fs"
import path from "path"
import process from "node:process"
import { spawnSync } from "child_process"
import { fileURLToPath } from "url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

const WHEELS_REQUIREMENTS_PATH = path.resolve(__dirname, "../requirements.txt")

const DIST_PYODIDE_DIR = path.resolve(__dirname, "../dist-pyodide")
const WHEELS_DIR = path.join(DIST_PYODIDE_DIR, "wheels")
const WHEELS_JSON_MANIFEST_PATH = path.join(WHEELS_DIR, "manifest.json")

function parseRequirements() {
  if (!fs.existsSync(WHEELS_REQUIREMENTS_PATH)) {
    throw new Error(`Cannot find ${WHEELS_REQUIREMENTS_PATH}`)
  }

  const source = fs.readFileSync(WHEELS_REQUIREMENTS_PATH, "utf8")
  const reqs = source
    .split("\n")
    .map(l => l.trim())
    .filter(l => l.length > 0 && !l.startsWith("#"))

  if (reqs.length === 0) {
    throw new Error(`No requirements found in ${WHEELS_REQUIREMENTS_PATH}`)
  }

  return { wheelReqs: reqs }
}

function parseReqSpec(spec) {
  const trimmed = String(spec).trim()
  const m = trimmed.match(/^([A-Za-z0-9][A-Za-z0-9._-]*)(?:==(.+))?$/)
  if (!m) return null
  return { name: m[1], version: m[2] ?? null }
}

function normalizeDistForWheel(name) {
  return name.toLowerCase().replace(/-/g, "_")
}

function indexWheelFiles() {
  if (!fs.existsSync(WHEELS_DIR)) {
    return []
  }
  return fs
    .readdirSync(WHEELS_DIR)
    .filter(f => f.endsWith(".whl"))
    .map(f => {
      const parts = f.split("-")
      const dist = parts[0] ?? ""
      const version = parts[1] ?? ""
      return {
        fileName: f,
        distNorm: normalizeDistForWheel(dist),
        version,
      }
    })
}

function resolveWheelFileForReq(wheelsIndex, reqSpec) {
  const req = parseReqSpec(reqSpec)
  if (!req?.name || !req.version) {
    throw new Error(
      `Requirement '${reqSpec}' must be pinned with '==<version>' to generate wheel file mapping.`,
    )
  }

  const distNorm = normalizeDistForWheel(req.name)
  const matches = wheelsIndex.filter(
    w => w.distNorm === distNorm && w.version === req.version,
  )

  if (matches.length === 0) {
    throw new Error(
      `Could not find wheel for ${req.name}==${req.version} under ${WHEELS_DIR}.`,
    )
  }
  if (matches.length > 1) {
    const files = matches.map(m => m.fileName).join(", ")
    throw new Error(
      `Multiple wheels match ${req.name}==${req.version} under ${WHEELS_DIR}: ${files}`,
    )
  }
  return matches[0].fileName
}

function writeManifest(localWheelFileNames) {
  const payload = {
    LOCAL_WHEELS: localWheelFileNames,
  }

  fs.mkdirSync(path.dirname(WHEELS_JSON_MANIFEST_PATH), { recursive: true })
  fs.writeFileSync(
    WHEELS_JSON_MANIFEST_PATH,
    JSON.stringify(payload, null, 2),
    "utf8",
  )
}

function downloadWheels(requirements, clean) {
  if (clean && fs.existsSync(WHEELS_DIR)) {
    fs.rmSync(WHEELS_DIR, { recursive: true, force: true })
  }
  fs.mkdirSync(WHEELS_DIR, { recursive: true })

  if (requirements.length === 0) return

  const result = spawnSync(
    "python3",
    [
      "-m",
      "pip",
      "download",
      "--only-binary=:all:",
      "--no-deps",
      "-d",
      WHEELS_DIR,
      ...requirements,
    ],
    { stdio: "inherit" },
  )

  if (result.status !== 0) {
    throw new Error(
      `pip download failed (exit code: ${result.status ?? "unknown"}).`,
    )
  }
}

function canResolveAllPinnedWheels(wheelsIndex, requirements) {
  try {
    for (const req of requirements) {
      resolveWheelFileForReq(wheelsIndex, req)
    }
    return true
  } catch {
    return false
  }
}

async function main() {
  const args = new Set(process.argv.slice(2))
  const clean = args.has("--clean")

  const { wheelReqs } = parseRequirements()
  const all = [...wheelReqs]

  console.log(
    `[Wheels] Syncing Python wheels to ${path.relative(process.cwd(), WHEELS_DIR)}${clean ? " (clean)" : ""}...`,
  )

  let wheelsIndex = indexWheelFiles()
  const needsDownload = clean || !canResolveAllPinnedWheels(wheelsIndex, all)

  if (needsDownload) {
    downloadWheels(all, clean)
    wheelsIndex = indexWheelFiles()
  }

  const localWheelFileNames = wheelReqs.map(r =>
    resolveWheelFileForReq(wheelsIndex, r),
  )

  writeManifest(localWheelFileNames)

  console.log(
    `[Wheels] Manifest written: ${path.relative(process.cwd(), WHEELS_JSON_MANIFEST_PATH)}`,
  )
}

main().catch(err => {
  console.error("[Wheels] Sync failed:", err)
  process.exitCode = 1
})
