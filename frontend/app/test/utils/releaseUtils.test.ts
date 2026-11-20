import { describe, expect, it } from "vitest"
import type { GitHubRelease } from "@/types/release"
import { isStableUpdateAvailable } from "@/utils/releaseUtils"

const nextBuild = "next-0.11.0-dev8-eeeeeeee"

function release(
  version: string,
  overrides?: Partial<GitHubRelease>,
): GitHubRelease {
  return {
    url: "",
    html_url: "",
    name: "",
    published_at: "",
    tag_name: `v${version}`,
    body: "Changes",
    assets: [],
    ...overrides,
  }
}

describe("stable update eligibility", () => {
  it("notifies stable builds on patch, minor, and major updates", () => {
    expect(isStableUpdateAvailable("0.11.0", release("0.11.1"))).toBe(true)
    expect(isStableUpdateAvailable("0.11.0", release("0.12.0"))).toBe(true)
    expect(isStableUpdateAvailable("0.11.0", release("1.0.0"))).toBe(true)
    expect(isStableUpdateAvailable("0.11.0", release("0.11.0"))).toBe(false)
  })

  it.each([
    ["0.10.9", false],
    ["0.11.0", false],
    ["0.11.1", false],
    ["0.11.9", false],
    ["0.12.0", true],
    ["0.12.1", true],
    ["1.0.0", true],
  ] as const)(
    "ignores patch updates and offers minor/major updates on next (%s -> %s)",
    (version, eligible) => {
      expect(isStableUpdateAvailable(nextBuild, release(version))).toBe(
        eligible,
      )
    },
  )

  it("rejects PR builds, drafts, and prerelease candidates", () => {
    expect(
      isStableUpdateAvailable("pr342-0.11.0-bbbaa888", release("0.12.0")),
    ).toBe(false)
    expect(
      isStableUpdateAvailable(nextBuild, release("0.12.0", { draft: true })),
    ).toBe(false)
    expect(
      isStableUpdateAvailable(
        nextBuild,
        release("0.12.0", { prerelease: true }),
      ),
    ).toBe(false)
  })
})
