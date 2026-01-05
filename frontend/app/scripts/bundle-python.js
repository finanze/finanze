/* global process */
import fs from "fs"
import path from "path"
import { spawnSync } from "child_process"
import { fileURLToPath } from "url"

const __filename = fileURLToPath(import.meta.url)
const __dirname = path.dirname(__filename)

// Configuration
const SOURCE_ROOT = path.resolve(__dirname, "../../../../finanze/finanze")
const CUSTOM_PYTHON_ROOT = path.resolve(__dirname, "../src/python")
const DIST_PYODIDE_ROOT = path.resolve(__dirname, "../dist-pyodide")
const WHEELS_ROOT = path.resolve(DIST_PYODIDE_ROOT, "wheels")
const PYODIDE_ROOT = path.resolve(DIST_PYODIDE_ROOT, "pyodide")
const DEST_ROOT = path.resolve(__dirname, "../dist/python")
const DEST_WHEELS_ROOT = path.resolve(DEST_ROOT, "wheels")
const DEST_PYODIDE_ROOT = path.resolve(__dirname, "../dist/pyodide")
const MINIFY_SCRIPT = path.resolve(__dirname, "./minify-python.py")
const INCLUDE_DIRS = [
  "infrastructure/controller/routes",
  "infrastructure/controller/mappers",
]
const EXCLUDED_DIRS = [
  "infrastructure/controller",
  "infrastructure/sheets",
  "infrastructure/file_storage",
  "infrastructure/credentials",
]

const EXCLUDED_FILES = ["server.py", "logs.py", "args.py", "__main__.py"]

const EXCLUDED_EXTENSIONS = [".pyc", ".pyo", ".pyd"]
const CACHE_DIRS = ["__pycache__", ".pytest_cache", ".git", ".ruff_cache"]

const CORE_PATTERNS = [
  "finanze/app.py",
  "finanze/app_core.py",
  "finanze/mobile_routes.py",
  "finanze/version.py",
  "finanze/logs.py",
  "finanze/quart.py",
  "init.py",
  "controller.py",
  "mobile_requirements.py",
  "finanze/domain/platform.py",
  "finanze/domain/status.py",
  "finanze/domain/user.py",
  "finanze/domain/data_init.py",
  "finanze/domain/dezimal.py",
  "finanze/domain/exception/",
  "finanze/domain/use_cases/get_status.py",
  "finanze/application/use_cases/get_status.py",
  "finanze/application/ports/data_manager.py",
  "finanze/application/ports/datasource_initiator.py",
  "finanze/application/ports/feature_flag_port.py",
  "finanze/application/ports/server_details_port.py",
  "finanze/application/ports/datasource_backup_port.py",
  "finanze/infrastructure/controller/router.py",
  "finanze/infrastructure/controller/handler.py",
  "finanze/infrastructure/controller/request_wrapper.py",
  "finanze/infrastructure/controller/routes/get_status.py",
  "finanze/infrastructure/repository/db/",
  "finanze/infrastructure/user_files/capacitor_data_manager.py",
  "finanze/infrastructure/user_files/user_data_manager.py",
  "finanze/infrastructure/config/capacitor_server_details_adapter.py",
  "finanze/infrastructure/client/features/",
  "finanze/infrastructure/file_storage/",
]

function isCoreFile(relativePath) {
  const normalized = relativePath.replace(/\\/g, "/")
  for (const pattern of CORE_PATTERNS) {
    if (pattern.endsWith("/")) {
      if (
        normalized.startsWith(pattern) ||
        normalized.includes(`/${pattern}`)
      ) {
        return true
      }
    } else {
      if (
        normalized === pattern ||
        normalized.endsWith(`/${pattern}`) ||
        normalized.endsWith(pattern)
      ) {
        return true
      }
    }
  }
  return false
}

// Ensure destination exists
if (fs.existsSync(DEST_ROOT)) {
  fs.rmSync(DEST_ROOT, { recursive: true, force: true })
}
fs.mkdirSync(DEST_ROOT, { recursive: true })

// Helper to check if directory should be excluded (only for SOURCE_ROOT)
function isExcludedDir(filePath) {
  const relativePath = path.relative(SOURCE_ROOT, filePath)

  // Inclusion override
  for (const includeDir of INCLUDE_DIRS) {
    if (
      relativePath === includeDir ||
      relativePath.startsWith(`${includeDir}${path.sep}`) ||
      includeDir.startsWith(`${relativePath}${path.sep}`)
    ) {
      return false
    }
  }

  for (const excludedDir of EXCLUDED_DIRS) {
    if (
      relativePath.includes(excludedDir) ||
      relativePath.startsWith(excludedDir)
    ) {
      return true
    }
  }

  return false
}

function isUnderInclude(relativePath) {
  return INCLUDE_DIRS.some(
    includeDir =>
      relativePath === includeDir ||
      relativePath.startsWith(`${includeDir}${path.sep}`),
  )
}

// Helper to check if file/cache should be excluded (applies to all roots)
function isExcludedFile(filePath) {
  // Check cache directories (always excluded)
  for (const cacheDir of CACHE_DIRS) {
    if (
      filePath.includes(`${path.sep}${cacheDir}${path.sep}`) ||
      filePath.includes(`${path.sep}${cacheDir}`)
    ) {
      return true
    }
  }

  // Check extensions (always excluded)
  const ext = path.extname(filePath)
  if (EXCLUDED_EXTENSIONS.includes(ext)) {
    return true
  }

  return false
}

// Collect files
const coreFileList = []
const deferredFileList = []

function copyRecursive(source, dest, rootPath, isCustom = false) {
  if (!fs.existsSync(source)) return

  const stats = fs.statSync(source)
  if (stats.isDirectory()) {
    // Always skip cache directories
    if (isExcludedFile(source)) return

    // Only apply directory exclusions to SOURCE_ROOT, not custom
    if (!isCustom && isExcludedDir(source)) return

    if (!fs.existsSync(dest)) {
      fs.mkdirSync(dest, { recursive: true })
    }

    const files = fs.readdirSync(source)
    for (const file of files) {
      copyRecursive(
        path.join(source, file),
        path.join(dest, file),
        rootPath,
        isCustom,
      )
    }
  } else {
    // Always check file exclusions (extensions, cache)
    if (isExcludedFile(source)) return

    // Check specific file exclusions (only for SOURCE_ROOT)
    if (!isCustom) {
      const fileName = path.basename(source)
      if (EXCLUDED_FILES.includes(fileName)) return

      const rel = path.relative(SOURCE_ROOT, source)
      const underExcluded = EXCLUDED_DIRS.some(
        dir => rel === dir || rel.startsWith(`${dir}${path.sep}`),
      )
      if (underExcluded && !isUnderInclude(rel)) return
    }

    // Only copy python files or strictly necessary data files
    if (!source.endsWith(".py")) return

    fs.copyFileSync(source, dest)

    // Add to manifest (path relative to DEST_ROOT)
    const relativeToDest = path.relative(DEST_ROOT, dest)
    if (isCoreFile(relativeToDest)) {
      coreFileList.push(relativeToDest)
    } else {
      deferredFileList.push(relativeToDest)
    }
  }
}

function copyWheels(sourceDir, destDir) {
  if (!fs.existsSync(sourceDir)) return
  fs.mkdirSync(destDir, { recursive: true })

  const entries = fs.readdirSync(sourceDir)
  for (const entry of entries) {
    const srcPath = path.join(sourceDir, entry)
    const stat = fs.statSync(srcPath)
    if (!stat.isFile()) continue

    // Keep it simple: copy wheels only.
    if (!entry.endsWith(".whl")) continue

    const dstPath = path.join(destDir, entry)
    fs.copyFileSync(srcPath, dstPath)
  }
}

function copyPyodideAssets(sourceDir, destDir) {
  if (!fs.existsSync(sourceDir)) return
  fs.mkdirSync(destDir, { recursive: true })

  const entries = fs.readdirSync(sourceDir)
  for (const entry of entries) {
    const srcPath = path.join(sourceDir, entry)
    const stat = fs.statSync(srcPath)
    if (stat.isDirectory()) {
      copyPyodideAssets(srcPath, path.join(destDir, entry))
    } else if (stat.isFile()) {
      fs.copyFileSync(srcPath, path.join(destDir, entry))
    }
  }
}

function minifyPythonFiles(destRoot) {
  if (process.env.FINANZE_PYTHON_MINIFY === "0") return

  const result = spawnSync("python3", [MINIFY_SCRIPT, destRoot], {
    stdio: "inherit",
  })
  if (result.status !== 0) {
    throw new Error(
      `Python minification failed (exit code: ${result.status ?? "unknown"}). Install dev requirements (python-minifier) or set FINANZE_PYTHON_MINIFY=0 to skip.`,
    )
  }
}

function readRequirementsFile(filePath) {
  if (!fs.existsSync(filePath)) return []

  const lines = fs
    .readFileSync(filePath, "utf8")
    .split("\n")
    .map(l => l.trim())
    .filter(l => l.length > 0 && !l.startsWith("#"))

  return lines
}

function generateWheelsManifestPy(destPythonDir, wheelsDir) {
  const jsonManifestPath = path.join(wheelsDir, "manifest.json")
  if (!fs.existsSync(jsonManifestPath)) return

  const payload = JSON.parse(fs.readFileSync(jsonManifestPath, "utf8"))
  const allWheels = Array.isArray(payload?.LOCAL_WHEELS)
    ? payload.LOCAL_WHEELS
    : []

  const coreWheelsReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-core.txt"),
  )
  const deferredWheelsReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-deferred.txt"),
  )
  const corePyodideReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-pyodide-core.txt"),
  )
  const deferredPyodideReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-pyodide-deferred.txt"),
  )

  function extractPackageName(req) {
    return req.split("==")[0].split(">=")[0].split("<=")[0].toLowerCase()
  }

  function wheelMatchesReqs(wheelFile, reqs) {
    const reqNames = reqs.map(extractPackageName)
    const wheelLower = wheelFile.toLowerCase()
    return reqNames.some(name => wheelLower.startsWith(name.replace(/-/g, "_")))
  }

  const coreWheels = allWheels.filter(w => wheelMatchesReqs(w, coreWheelsReqs))
  const deferredWheels = allWheels.filter(w =>
    wheelMatchesReqs(w, deferredWheelsReqs),
  )

  const lines = []
  lines.push("# Generated by scripts/bundle-python.js. DO NOT EDIT.")
  lines.push("")

  lines.push("LOCAL_WHEELS_CORE = [")
  for (const f of coreWheels) {
    lines.push(`    "/python/wheels/${f}",`)
  }
  lines.push("]")
  lines.push("")

  lines.push("LOCAL_WHEELS_DEFERRED = [")
  for (const f of deferredWheels) {
    lines.push(`    "/python/wheels/${f}",`)
  }
  lines.push("]")
  lines.push("")

  lines.push("PYODIDE_PACKAGES_CORE = [")
  for (const req of corePyodideReqs) {
    lines.push(`    ${JSON.stringify(req)},`)
  }
  lines.push("]")
  lines.push("")

  lines.push("PYODIDE_PACKAGES_DEFERRED = [")
  for (const req of deferredPyodideReqs) {
    lines.push(`    ${JSON.stringify(req)},`)
  }
  lines.push("]")
  lines.push("")

  fs.writeFileSync(
    path.join(destPythonDir, "wheels_manifest.py"),
    lines.join("\n"),
    "utf8",
  )
}

console.log(`Bundling Python modules from ${SOURCE_ROOT} to ${DEST_ROOT}...`)

copyRecursive(SOURCE_ROOT, path.join(DEST_ROOT, "finanze"), DEST_ROOT)

if (fs.existsSync(CUSTOM_PYTHON_ROOT)) {
  console.log(`Bundling custom Python modules from ${CUSTOM_PYTHON_ROOT}...`)
  copyRecursive(CUSTOM_PYTHON_ROOT, DEST_ROOT, DEST_ROOT, true)
}

if (fs.existsSync(WHEELS_ROOT)) {
  console.log(
    `Bundling Python wheels from ${WHEELS_ROOT} to ${DEST_WHEELS_ROOT}...`,
  )
  copyWheels(WHEELS_ROOT, DEST_WHEELS_ROOT)
  generateWheelsManifestPy(DEST_ROOT, WHEELS_ROOT)
}

if (fs.existsSync(PYODIDE_ROOT)) {
  console.log(
    `Bundling Pyodide assets from ${PYODIDE_ROOT} to ${DEST_PYODIDE_ROOT}...`,
  )
  if (fs.existsSync(DEST_PYODIDE_ROOT)) {
    fs.rmSync(DEST_PYODIDE_ROOT, { recursive: true, force: true })
  }
  copyPyodideAssets(PYODIDE_ROOT, DEST_PYODIDE_ROOT)
}

minifyPythonFiles(DEST_ROOT)

const manifestCore = {
  files: coreFileList,
}

const manifestDeferred = {
  files: deferredFileList,
}

fs.writeFileSync(
  path.join(DEST_ROOT, "manifest_core.json"),
  JSON.stringify(manifestCore, null, 2),
)

fs.writeFileSync(
  path.join(DEST_ROOT, "manifest_deferred.json"),
  JSON.stringify(manifestDeferred, null, 2),
)

const totalFiles = coreFileList.length + deferredFileList.length
console.log(
  `Bundle complete. ${totalFiles} files copied (${coreFileList.length} core, ${deferredFileList.length} deferred).`,
)
console.log(
  `Manifests written to ${path.join(DEST_ROOT, "manifest_core.json")} and manifest_deferred.json`,
)
