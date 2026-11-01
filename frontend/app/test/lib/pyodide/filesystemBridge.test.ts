import { beforeEach, describe, expect, it, vi } from "vitest"

const filesystemMocks = vi.hoisted(() => ({
  mkdir: vi.fn(),
  stat: vi.fn(),
}))

vi.mock("@capacitor/core", () => ({
  Capacitor: {
    convertFileSrc: (uri: string) => uri,
    getPlatform: () => "ios",
  },
}))

vi.mock("@capacitor/filesystem", () => ({
  Directory: { Documents: "DOCUMENTS" },
  Encoding: { UTF8: "utf8" },
  Filesystem: filesystemMocks,
}))

import { filesystemBridge } from "@/lib/pyodide/bridges/filesystemBridge"

describe("filesystemBridge.createDirectory", () => {
  beforeEach(() => {
    filesystemMocks.mkdir.mockReset()
    filesystemMocks.stat.mockReset()
  })

  it("does not call mkdir when the directory already exists", async () => {
    filesystemMocks.stat.mockResolvedValue({ type: "directory" })

    await filesystemBridge.createDirectory("crypto_cache")

    expect(filesystemMocks.stat).toHaveBeenCalledWith({
      path: "finanze_uploads/crypto_cache",
      directory: "DOCUMENTS",
    })
    expect(filesystemMocks.mkdir).not.toHaveBeenCalled()
  })

  it("creates the directory when it does not exist", async () => {
    filesystemMocks.stat.mockRejectedValue(new Error("Not found"))
    filesystemMocks.mkdir.mockResolvedValue(undefined)

    await filesystemBridge.createDirectory("crypto_cache")

    expect(filesystemMocks.mkdir).toHaveBeenCalledWith({
      path: "finanze_uploads/crypto_cache",
      directory: "DOCUMENTS",
      recursive: true,
    })
  })

  it("accepts another concurrent call creating the same directory", async () => {
    const alreadyExists = new Error("Already exists")
    filesystemMocks.stat
      .mockRejectedValueOnce(new Error("Not found"))
      .mockResolvedValueOnce({ type: "directory" })
    filesystemMocks.mkdir.mockRejectedValue(alreadyExists)

    await expect(
      filesystemBridge.createDirectory("crypto_cache"),
    ).resolves.toBeUndefined()
  })

  it("propagates mkdir failures when the directory remains absent", async () => {
    const mkdirError = new Error("Permission denied")
    filesystemMocks.stat.mockRejectedValue(new Error("Not found"))
    filesystemMocks.mkdir.mockRejectedValue(mkdirError)

    await expect(filesystemBridge.createDirectory("crypto_cache")).rejects.toBe(
      mkdirError,
    )
  })
})
