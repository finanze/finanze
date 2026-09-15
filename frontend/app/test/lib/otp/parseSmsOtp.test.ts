import { describe, expect, it } from "vitest"

import { parseSmsOtp } from "@/lib/otp/parseSmsOtp"

describe("parseSmsOtp", () => {
  it("returns unique 6-digit code", () => {
    expect(parseSmsOtp("Tu codigo Wecity es 123456. No lo compartas.", 6)).toBe(
      "123456",
    )
  })

  it("returns unique 4-digit code", () => {
    expect(parseSmsOtp("Trade Republic code: 4821", 4)).toBe("4821")
  })

  it("returns null when two unlabeled codes of the same length exist", () => {
    expect(parseSmsOtp("Use 123456 or 654321", 6)).toBeNull()
  })

  it("prefers a labeled code when another same-length number exists", () => {
    expect(parseSmsOtp("Code 123456 sent to 654321", 6)).toBe("123456")
  })

  it("ignores longer digit runs without word boundaries", () => {
    expect(parseSmsOtp("ref 1234567 extra", 6)).toBeNull()
  })

  it("does not treat a 6-digit code as a 4-digit code", () => {
    expect(parseSmsOtp("Your code is 123456", 4)).toBeNull()
  })

  it("uses a custom capturing pattern", () => {
    expect(
      parseSmsOtp("OTP: AB-482911 end", 6, "OTP:\\s*[A-Z]{2}-(\\d{6})"),
    ).toBe("482911")
  })

  it("rejects a pattern capture that is not the pin length", () => {
    expect(parseSmsOtp("OTP: 1234", 6, "OTP:\\s*(\\d+)")).toBeNull()
  })

  it("returns null for an invalid pattern", () => {
    expect(parseSmsOtp("code 123456", 6, "(")).toBeNull()
  })

  it("returns null for empty message", () => {
    expect(parseSmsOtp("", 6)).toBeNull()
  })

  it("returns null when pattern has no capture group", () => {
    expect(parseSmsOtp("code 123456", 6, "\\d{6}")).toBeNull()
  })
})
