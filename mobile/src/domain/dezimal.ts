import Decimal from "decimal.js"

export function parseDezimalValue(value: unknown): Dezimal {
  if (value == null) return Dezimal.zero()
  if (value instanceof Dezimal) return value

  if (typeof value === "string") {
    const trimmed = value.trim()
    if (!trimmed) return Dezimal.zero()
    try {
      return Dezimal.fromString(trimmed)
    } catch {
      return Dezimal.zero()
    }
  }

  if (typeof value === "number") {
    if (!Number.isFinite(value)) return Dezimal.zero()
    try {
      return Dezimal.fromFloat(value)
    } catch {
      return Dezimal.zero()
    }
  }

  if (typeof value === "bigint") {
    try {
      return Dezimal.fromString(value.toString())
    } catch {
      return Dezimal.zero()
    }
  }

  if (typeof value === "object" && value && "val" in (value as any)) {
    return parseDezimalValue((value as any).val)
  }

  return Dezimal.zero()
}

export class Dezimal {
  readonly val: Decimal

  private constructor(value: Decimal) {
    this.val = value
  }

  static zero(): Dezimal {
    return new Dezimal(new Decimal(0))
  }

  static fromDecimal(value: Decimal): Dezimal {
    return new Dezimal(new Decimal(value))
  }

  // Explicit boundary conversions (keeps the rest of the app Dezimal-only)
  static fromFloat(value: number): Dezimal {
    if (!Number.isFinite(value)) throw new Error("Invalid float")
    // Match Python: Decimal(str(float))
    return new Dezimal(new Decimal(value.toString()))
  }

  static fromInt(value: number): Dezimal {
    if (!Number.isFinite(value) || !Number.isInteger(value)) {
      throw new Error("Invalid int")
    }
    return new Dezimal(new Decimal(value))
  }

  static fromString(value: string): Dezimal {
    return new Dezimal(new Decimal(value))
  }

  toString(): string {
    return this.val.toString()
  }

  toJSON(): string {
    return this.toString()
  }

  toNumber(): number {
    return this.val.toNumber()
  }

  isFinite(): boolean {
    return this.val.isFinite()
  }

  isZero(): boolean {
    return this.val.isZero()
  }

  isNegative(): boolean {
    return this.val.isNegative()
  }

  gt(other: Dezimal): boolean {
    return this.val.comparedTo(other.val) === 1
  }

  lt(other: Dezimal): boolean {
    return this.val.comparedTo(other.val) === -1
  }

  le(other: Dezimal): boolean {
    const c = this.val.comparedTo(other.val)
    return c === -1 || c === 0
  }

  ge(other: Dezimal): boolean {
    const c = this.val.comparedTo(other.val)
    return c === 1 || c === 0
  }

  eq(other: Dezimal): boolean {
    return this.val.comparedTo(other.val) === 0
  }

  add(other: Dezimal): Dezimal {
    return new Dezimal(this.val.add(other.val))
  }

  sub(other: Dezimal): Dezimal {
    return new Dezimal(this.val.sub(other.val))
  }

  mul(other: Dezimal): Dezimal {
    return new Dezimal(this.val.mul(other.val))
  }

  truediv(other: Dezimal): Dezimal {
    return new Dezimal(this.val.div(other.val))
  }

  floordiv(other: Dezimal): Dezimal {
    return new Dezimal(this.val.div(other.val).floor())
  }

  pow(other: Dezimal): Dezimal {
    return new Dezimal(this.val.pow(other.val))
  }

  mod(other: Dezimal): Dezimal {
    return new Dezimal(this.val.mod(other.val))
  }

  round(ndigits: number): Dezimal {
    return new Dezimal(
      this.val.toDecimalPlaces(ndigits, Decimal.ROUND_HALF_EVEN),
    )
  }

  neg(): Dezimal {
    return new Dezimal(this.val.neg())
  }

  abs(): Dezimal {
    return new Dezimal(this.val.abs())
  }
}
