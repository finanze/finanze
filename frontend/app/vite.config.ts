import { rmSync, statSync, createReadStream, readFileSync } from "node:fs"
import { spawn } from "node:child_process"
import { defineConfig, loadEnv } from "vite"
import react from "@vitejs/plugin-react"
import { sentryVitePlugin } from "@sentry/vite-plugin"
import { resolve, sep } from "node:path"
import { createRequire } from "node:module"
import pkg from "./package.json"

const require = createRequire(import.meta.url)

export default defineConfig(({ command, mode }) => {
  const env = loadEnv(mode, __dirname, "")
  const isMobileDev = mode === "mobile" || process.env.MOBILE_DEV === "1"
  const isMobileBuild = process.env.MOBILE_BUILD === "1"
  const isMobile = isMobileDev || isMobileBuild
  const includeConnections = process.env.INCLUDE_CONNECTIONS !== "0"
  if (!isMobile) {
    rmSync("dist-electron", { recursive: true, force: true })
  }

  const isServe = command === "serve"
  const isBuild = command === "build"
  const sourcemap = isServe || !!process.env.VSCODE_DEBUG

  const serverFromUrl = (
    urlString: string | undefined,
    fallback: { host: string; port: number } = {
      host: "localhost",
      port: 5173,
    },
    strictPort: boolean = false,
  ) => {
    try {
      if (!urlString) return { ...fallback, strictPort }
      const url = new URL(urlString)
      return {
        host: url.hostname || fallback.host,
        port: url.port ? +url.port : fallback.port,
        strictPort,
      }
    } catch {
      return { ...fallback, strictPort }
    }
  }

  const mobileServer =
    isMobileDev && isServe ? serverFromUrl(env.VITE_DEV_SERVER_URL) : undefined

  const vscodeServer = process.env.VSCODE_DEBUG
    ? serverFromUrl((pkg as any)?.debug?.env?.VITE_DEV_SERVER_URL)
    : undefined

  const electronExternals = ["electron"]

  const electronPlugin = !isMobile
    ? (require("vite-plugin-electron/simple") as { default: any }).default
    : null

  // npm_package_version is unset under `pnpm exec`, which package.py uses.
  const appVersion: string = JSON.parse(
    readFileSync(resolve(__dirname, "package.json"), "utf-8"),
  ).version

  // Stack traces reaching Better Stack are minified unless the maps are uploaded.
  const sourceMapAuthToken = env.BETTER_STACK_API_TOKEN
  const uploadSourceMaps = isBuild && !!sourceMapAuthToken

  if (isBuild) {
    console.log(
      uploadSourceMaps
        ? `[sourcemaps] uploading to Better Stack (release ${appVersion})`
        : "[sourcemaps] upload skipped, BETTER_STACK_API_TOKEN is not set",
    )
  }

  return {
    define: {
      __MOBILE__: JSON.stringify(isMobile),
      __CONNECTIONS__: JSON.stringify(includeConnections),
      __APP_VERSION__: JSON.stringify(appVersion),
    },
    resolve: {
      alias: {
        "@": resolve(__dirname, "./src"),
      },
    },
    plugins: [
      react(),
      ...(!isMobileDev && electronPlugin
        ? [
            electronPlugin({
              main: {
                entry: "electron/main/index.ts",
                vite: {
                  define: {
                    __APP_VERSION__: JSON.stringify(appVersion),
                    __BS_ELECTRON_MAIN_DSN__: JSON.stringify(
                      env.VITE_BS_ELECTRON_MAIN_DSN ?? "",
                    ),
                    __BS_DESKTOP_BACKEND_DSN__: JSON.stringify(
                      env.VITE_BS_DESKTOP_BACKEND_DSN ?? "",
                    ),
                    __BS_ENVIRONMENT__: JSON.stringify(
                      env.VITE_BS_ENVIRONMENT ||
                        (isBuild ? "production" : "development"),
                    ),
                  },
                  build: {
                    sourcemap: uploadSourceMaps ? "hidden" : sourcemap,
                    minify: isBuild,
                    outDir: "dist-electron/main",
                    rollupOptions: {
                      external: electronExternals,
                    },
                  },
                  plugins: uploadSourceMaps
                    ? [
                        sentryVitePlugin({
                          org: env.BETTER_STACK_SOURCEMAP_ORG,
                          project: env.BETTER_STACK_SOURCEMAP_PROJECT,
                          url: env.BETTER_STACK_SOURCEMAP_URL,
                          authToken: sourceMapAuthToken,
                          release: { name: appVersion },
                          sourcemaps: {
                            filesToDeleteAfterUpload: [
                              "dist-electron/main/**/*.map",
                            ],
                          },
                        }),
                      ]
                    : [],
                },
              },
              preload: {
                input: "electron/preload/index.ts",
                vite: {
                  build: {
                    sourcemap: sourcemap ? "inline" : undefined,
                    minify: isBuild,
                    outDir: "dist-electron/preload",
                    rollupOptions: {
                      external: electronExternals,
                      output: {
                        inlineDynamicImports: true,
                      },
                    },
                  },
                },
              },
            }),
          ]
        : []),
      ...(isMobileDev && isServe
        ? [
            {
              name: "watch-python",
              configureServer(server) {
                const pythonSrcDir = resolve(__dirname, "./src/python")
                let isBuilding = false

                server.watcher.add(pythonSrcDir + "/**")

                server.watcher.on("change", file => {
                  if (file.startsWith(pythonSrcDir) && !isBuilding) {
                    isBuilding = true
                    console.log("[Python] Rebuilding Python bundle...")

                    const proc = spawn("pnpm", ["run", "build:python"], {
                      cwd: __dirname,
                      stdio: "inherit",
                      shell: true,
                    })

                    proc.on("close", code => {
                      isBuilding = false
                      if (code === 0) {
                        console.log("[Python] Bundle rebuilt successfully")
                        server.ws.send({ type: "full-reload" })
                      } else {
                        console.error(
                          `[Python] Bundle build failed with code ${code}`,
                        )
                      }
                    })
                  }
                })
              },
            },
          ]
        : []),
      ...(isMobileDev && isServe
        ? [
            {
              name: "serve-sqljs-wasm-dev",
              configureServer(server) {
                const sqljsDistDir = resolve(
                  __dirname,
                  "./node_modules/sql.js/dist",
                )

                const assets: Array<{
                  suffix: string
                  file: string
                  contentType: string
                }> = [
                  {
                    suffix: "/sql-wasm.wasm",
                    file: "sql-wasm.wasm",
                    contentType: "application/wasm",
                  },
                  {
                    suffix: "/sql-wasm.js",
                    file: "sql-wasm.js",
                    contentType: "application/javascript",
                  },
                  {
                    suffix: "/sql-wasm-debug.wasm",
                    file: "sql-wasm-debug.wasm",
                    contentType: "application/wasm",
                  },
                  {
                    suffix: "/sql-wasm-debug.js",
                    file: "sql-wasm-debug.js",
                    contentType: "application/javascript",
                  },
                ]

                server.middlewares.use((req, res, next) => {
                  if (!req.url) return next()

                  const urlPath = req.url.split("?")[0]
                  const asset = assets.find(a => urlPath.endsWith(a.suffix))
                  if (!asset) return next()

                  const filePath = resolve(sqljsDistDir, asset.file)

                  try {
                    const stat = statSync(filePath)
                    if (!stat.isFile()) return next()

                    res.statusCode = 200
                    res.setHeader("Content-Type", asset.contentType)
                    res.setHeader("Cache-Control", "no-store")
                    res.setHeader("Content-Length", stat.size)
                    createReadStream(filePath).pipe(res)
                    return
                  } catch {
                    return next()
                  }
                })
              },
            },
          ]
        : []),
      {
        name: "serve-offline-assets-dev",
        configureServer(server) {
          const serveFromDir = (
            mountPath: string,
            rootDir: string,
            contentTypeForFile: (filePath: string) => string | undefined,
          ) => {
            server.middlewares.use(mountPath, (req, res, next) => {
              if (!req.url) return next()

              const urlPath = req.url.split("?")[0]
              const relativePath = urlPath.replace(/^\//, "")
              const filePath = resolve(rootDir, relativePath)

              const rootWithSep = rootDir.endsWith(sep)
                ? rootDir
                : rootDir + sep
              if (!filePath.startsWith(rootWithSep)) {
                res.statusCode = 403
                res.setHeader("Content-Type", "text/plain")
                res.end("Forbidden")
                return
              }

              try {
                const stat = statSync(filePath)
                if (!stat.isFile()) return next()

                res.statusCode = 200
                res.setHeader("Cache-Control", "no-store")
                res.setHeader("Content-Length", stat.size)

                const ct = contentTypeForFile(filePath)
                if (ct) res.setHeader("Content-Type", ct)

                createReadStream(filePath).pipe(res)
                return
              } catch {
                return next()
              }
            })
          }

          serveFromDir(
            "/python",
            resolve(__dirname, "./dist/python"),
            (filePath: string) => {
              if (filePath.endsWith(".py")) return "text/plain"
              if (filePath.endsWith(".json")) return "application/json"
              if (filePath.endsWith(".txt")) return "text/plain"
              return undefined
            },
          )

          serveFromDir(
            "/pyodide",
            resolve(__dirname, "./dist-pyodide/pyodide"),
            (filePath: string) => {
              if (filePath.endsWith(".wasm")) return "application/wasm"
              if (filePath.endsWith(".mjs") || filePath.endsWith(".js")) {
                return "application/javascript"
              }
              if (filePath.endsWith(".json")) return "application/json"
              if (filePath.endsWith(".zip")) return "application/zip"
              return undefined
            },
          )
        },
      },
      ...(uploadSourceMaps
        ? [
            sentryVitePlugin({
              org: env.BETTER_STACK_SOURCEMAP_ORG,
              project: env.BETTER_STACK_SOURCEMAP_PROJECT,
              url: env.BETTER_STACK_SOURCEMAP_URL,
              authToken: sourceMapAuthToken,
              release: { name: appVersion },
              sourcemaps: {
                filesToDeleteAfterUpload: ["dist/**/*.map"],
              },
            }),
          ]
        : []),
    ],
    // Pyodide worker uses code-splitting; Rollup can't emit multi-chunk IIFE/UMD.
    // Force ES module output for worker bundles.
    worker: {
      format: "es",
    },
    build: {
      sourcemap: uploadSourceMaps ? "hidden" : sourcemap,
      rollupOptions: {
        input: {
          main: resolve(__dirname, "index.html"),
          about: resolve(__dirname, "about.html"),
        },
        external: isMobile
          ? [
              "electron",
              "electron-updater",
              "electron-window-state",
              "electron-is-dev",
            ]
          : ["sql.js", "jeep-sqlite"],
      },
    },
    server: mobileServer || vscodeServer,
  }
})
