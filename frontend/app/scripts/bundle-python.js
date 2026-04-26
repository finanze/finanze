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

const INCLUDE_CONNECTIONS = process.env.INCLUDE_CONNECTIONS !== "0"

const CONNECTION_EXCLUDED_PATTERNS = [
  "infrastructure/client/entity/crypto/",
  "infrastructure/client/entity/financial/",
  "infrastructure/client/entity/exchange/",
  "infrastructure/client/entity/psd2/",
]

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
  "finanze/infrastructure/file_storage/preference_exchange_storage.py",
]

const LAZY_PATTERNS = [
  "finanze/app_lazy.py",
  // Infrastructure - entity fetchers & crypto
  "finanze/infrastructure/client/entity/crypto/",
  "finanze/infrastructure/client/entity/financial/",
  "finanze/infrastructure/client/entity/exchange/",
  "finanze/infrastructure/client/crypto/",
  "finanze/infrastructure/crypto/",
  // Infrastructure - table, templating, interests, keychain, backup processor, file storage (mobile)
  "finanze/infrastructure/table/xlsx_file_table_adapter.py",
  "finanze/infrastructure/templating/",
  "finanze/infrastructure/client/interests/",
  "finanze/infrastructure/client/keychain/",
  "finanze/infrastructure/keychain/",
  "finanze/infrastructure/cloud/backup/capacitor_backup_processor.py",
  "finanze/infrastructure/file_storage/mobile_file_storage.py",
  // Infrastructure - repositories (lazy-only)
  "finanze/infrastructure/repository/keychain/",
  "finanze/infrastructure/repository/historic/",
  "finanze/infrastructure/repository/sessions/",
  "finanze/infrastructure/repository/crypto/crypto_asset_repository.py",
  "finanze/infrastructure/repository/templates/",
  // Use cases (original 9)
  "finanze/application/use_cases/add_entity_credentials.py",
  "finanze/application/use_cases/connect_crypto_wallet.py",
  "finanze/application/use_cases/derive_crypto_addresses.py",
  "finanze/application/use_cases/export_file.py",
  "finanze/application/use_cases/fetch_crypto_data.py",
  "finanze/application/use_cases/fetch_financial_data.py",
  "finanze/application/use_cases/import_file.py",
  "finanze/application/use_cases/import_backup.py",
  "finanze/application/use_cases/upload_backup.py",
  // Use cases (expanded lazy)
  "finanze/application/use_cases/update_settings.py",
  "finanze/application/use_cases/disconnect_entity.py",
  "finanze/application/use_cases/update_crypto_wallet.py",
  "finanze/application/use_cases/delete_crypto_wallet.py",
  "finanze/application/use_cases/save_commodities.py",
  "finanze/application/use_cases/connect_external_integration.py",
  "finanze/application/use_cases/disconnect_external_integration.py",
  "finanze/application/use_cases/save_periodic_flow.py",
  "finanze/application/use_cases/update_periodic_flow.py",
  "finanze/application/use_cases/delete_periodic_flow.py",
  "finanze/application/use_cases/save_pending_flows.py",
  "finanze/application/use_cases/create_real_estate.py",
  "finanze/application/use_cases/update_real_estate.py",
  "finanze/application/use_cases/delete_real_estate.py",
  "finanze/application/use_cases/calculate_loan.py",
  "finanze/application/use_cases/calculate_savings.py",
  "finanze/application/use_cases/get_euribor_rates.py",
  "finanze/application/use_cases/forecast.py",
  "finanze/application/use_cases/update_contributions.py",
  "finanze/application/use_cases/update_position.py",
  "finanze/application/use_cases/add_manual_transaction.py",
  "finanze/application/use_cases/update_manual_transaction.py",
  "finanze/application/use_cases/delete_manual_transaction.py",
  "finanze/application/use_cases/get_historic.py",
  "finanze/application/use_cases/get_instruments.py",
  "finanze/application/use_cases/get_instrument_info.py",
  "finanze/application/use_cases/search_crypto_assets.py",
  "finanze/application/use_cases/get_crypto_asset_details.py",
  "finanze/application/use_cases/get_templates.py",
  "finanze/application/use_cases/create_template.py",
  "finanze/application/use_cases/update_template.py",
  "finanze/application/use_cases/delete_template.py",
  "finanze/application/use_cases/get_template_fields.py",
  "finanze/application/use_cases/save_backup_settings.py",
  // Route handlers (original 9)
  "finanze/infrastructure/controller/routes/add_entity_login.py",
  "finanze/infrastructure/controller/routes/fetch_financial_data.py",
  "finanze/infrastructure/controller/routes/fetch_crypto_data.py",
  "finanze/infrastructure/controller/routes/import_file.py",
  "finanze/infrastructure/controller/routes/export_file.py",
  "finanze/infrastructure/controller/routes/connect_crypto_wallet.py",
  "finanze/infrastructure/controller/routes/derive_crypto_addresses.py",
  "finanze/infrastructure/controller/routes/upload_backup.py",
  "finanze/infrastructure/controller/routes/import_backup.py",
  // Route handlers (expanded lazy)
  "finanze/infrastructure/controller/routes/update_settings.py",
  "finanze/infrastructure/controller/routes/disconnect_entity.py",
  "finanze/infrastructure/controller/routes/update_crypto_wallet.py",
  "finanze/infrastructure/controller/routes/delete_crypto_wallet.py",
  "finanze/infrastructure/controller/routes/save_commodities.py",
  "finanze/infrastructure/controller/routes/connect_external_integration.py",
  "finanze/infrastructure/controller/routes/disconnect_external_integration.py",
  "finanze/infrastructure/controller/routes/save_periodic_flow.py",
  "finanze/infrastructure/controller/routes/update_periodic_flow.py",
  "finanze/infrastructure/controller/routes/delete_periodic_flow.py",
  "finanze/infrastructure/controller/routes/save_pending_flows.py",
  "finanze/infrastructure/controller/routes/create_real_estate.py",
  "finanze/infrastructure/controller/routes/update_real_estate.py",
  "finanze/infrastructure/controller/routes/delete_real_estate.py",
  "finanze/infrastructure/controller/routes/calculate_loan.py",
  "finanze/infrastructure/controller/routes/calculate_savings.py",
  "finanze/infrastructure/controller/routes/get_euribor_rates.py",
  "finanze/infrastructure/controller/routes/forecast.py",
  "finanze/infrastructure/controller/routes/update_contributions.py",
  "finanze/infrastructure/controller/routes/update_position.py",
  "finanze/infrastructure/controller/routes/add_manual_transaction.py",
  "finanze/infrastructure/controller/routes/update_manual_transaction.py",
  "finanze/infrastructure/controller/routes/delete_manual_transaction.py",
  "finanze/infrastructure/controller/routes/historic.py",
  "finanze/infrastructure/controller/routes/instruments.py",
  "finanze/infrastructure/controller/routes/instrument_details.py",
  "finanze/infrastructure/controller/routes/search_crypto_assets.py",
  "finanze/infrastructure/controller/routes/get_crypto_asset_details.py",
  "finanze/infrastructure/controller/routes/get_templates.py",
  "finanze/infrastructure/controller/routes/create_template.py",
  "finanze/infrastructure/controller/routes/update_template.py",
  "finanze/infrastructure/controller/routes/delete_template.py",
  "finanze/infrastructure/controller/routes/get_template_fields_route.py",
  "finanze/infrastructure/controller/routes/save_backup_settings.py",
]

function matchesPatterns(relativePath, patterns) {
  const normalized = relativePath.replace(/\\/g, "/")
  for (const pattern of patterns) {
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

function isCoreFile(relativePath) {
  return matchesPatterns(relativePath, CORE_PATTERNS)
}

function isLazyFile(relativePath) {
  return matchesPatterns(relativePath, LAZY_PATTERNS)
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
const lazyFileList = []

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
    if (!source.endsWith(".py") && !source.endsWith(".pkl")) return

    // Exclude connection-related files in store builds
    if (!INCLUDE_CONNECTIONS) {
      const relToCheck = isCustom
        ? path.relative(CUSTOM_PYTHON_ROOT, source)
        : path.relative(SOURCE_ROOT, source)
      if (matchesPatterns(relToCheck, CONNECTION_EXCLUDED_PATTERNS)) return
    }

    fs.copyFileSync(source, dest)

    // Add to manifest (path relative to DEST_ROOT)
    const relativeToDest = path.relative(DEST_ROOT, dest)
    if (isCoreFile(relativeToDest)) {
      coreFileList.push(relativeToDest)
    } else if (isLazyFile(relativeToDest)) {
      lazyFileList.push(relativeToDest)
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
  const lazyWheelsReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-lazy.txt"),
  )
  const corePyodideReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-pyodide-core.txt"),
  )
  const deferredPyodideReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-pyodide-deferred.txt"),
  )
  const lazyPyodideReqs = readRequirementsFile(
    path.resolve(__dirname, "../requirements-pyodide-lazy.txt"),
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
  const lazyWheels = allWheels.filter(w => wheelMatchesReqs(w, lazyWheelsReqs))

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

  lines.push("LOCAL_WHEELS_LAZY = [")
  for (const f of lazyWheels) {
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

  lines.push("PYODIDE_PACKAGES_LAZY = [")
  for (const req of lazyPyodideReqs) {
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

fs.writeFileSync(
  path.join(DEST_ROOT, "finanze", "build_config.py"),
  `INCLUDE_CONNECTIONS = ${INCLUDE_CONNECTIONS ? "True" : "False"}\n`,
  "utf8",
)
coreFileList.push("finanze/build_config.py")

const manifestCore = {
  files: coreFileList,
}

const manifestDeferred = {
  files: deferredFileList,
}

const manifestLazy = {
  files: lazyFileList,
}

fs.writeFileSync(
  path.join(DEST_ROOT, "manifest_core.json"),
  JSON.stringify(manifestCore, null, 2),
)

fs.writeFileSync(
  path.join(DEST_ROOT, "manifest_deferred.json"),
  JSON.stringify(manifestDeferred, null, 2),
)

fs.writeFileSync(
  path.join(DEST_ROOT, "manifest_lazy.json"),
  JSON.stringify(manifestLazy, null, 2),
)

const totalFiles =
  coreFileList.length + deferredFileList.length + lazyFileList.length
console.log(
  `Bundle complete. ${totalFiles} files copied (${coreFileList.length} core, ${deferredFileList.length} deferred, ${lazyFileList.length} lazy).`,
)
console.log(
  `Manifests written to ${path.join(DEST_ROOT, "manifest_core.json")} and manifest_deferred.json`,
)
