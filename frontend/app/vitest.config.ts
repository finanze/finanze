import path from "path"
import { defineConfig } from "vitest/config"

export default defineConfig({
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "src"),
    },
  },
  test: {
    root: __dirname,
    environment: "jsdom",
    include: ["test/**/*.{test,spec}.?(c|m)[jt]s?(x)"],
    setupFiles: ["test/setup.ts"],
    testTimeout: 1000 * 29,
  },
})
