declare module "aes-js" {
  // Minimal typing shim for aes-js v3 used in CBC decrypt.
  // We only type what we use.
  export namespace ModeOfOperation {
    class cbc {
      constructor(key: Uint8Array, iv: Uint8Array)
      decrypt(data: Uint8Array): Uint8Array
    }
  }
}
