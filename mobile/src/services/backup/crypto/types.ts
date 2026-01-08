import { Buffer } from "buffer"

export type DeriveKeyMeta = {
  cacheHit: boolean
  ms: number
  iterations: number
  native: boolean
}

export type FernetDecryptMeta = {
  ms: number
  native: boolean
}

export type DeriveKeyResult = {
  key: Buffer
  meta: DeriveKeyMeta
}

export type FernetDecryptResult = {
  plaintext: Buffer
  meta: FernetDecryptMeta
}
