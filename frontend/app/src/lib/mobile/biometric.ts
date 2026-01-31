export enum BiometricType {
  NONE = "none",
  FACE = "face",
  FINGERPRINT = "fingerprint",
  MULTIPLE = "multiple",
}

export interface BiometricAvailability {
  isAvailable: boolean
  biometricType: BiometricType
  errorMessage?: string
}

export interface BiometricCredentials {
  username: string
  password: string
}

const BIOMETRIC_SERVER = "finanze-app"

type NativeBiometricApi = {
  isAvailable: (...args: any[]) => Promise<any>
  verifyIdentity: (...args: any[]) => Promise<any>
  setCredentials: (...args: any[]) => Promise<any>
  getCredentials: (...args: any[]) => Promise<any>
  deleteCredentials: (...args: any[]) => Promise<any>
  isCredentialsSaved: (...args: any[]) => Promise<any>
  getPluginVersion: (...args: any[]) => Promise<any>
}

let cachedNativeBiometric: NativeBiometricApi | null | undefined

async function getNativeBiometric(): Promise<NativeBiometricApi | null> {
  if (!__MOBILE__) return null
  if (cachedNativeBiometric !== undefined) return cachedNativeBiometric

  try {
    const mod = await import("@capgo/capacitor-native-biometric")
    const plugin: any = (mod as any).NativeBiometric
    if (!plugin) {
      cachedNativeBiometric = null
      return null
    }

    // IMPORTANT: Capacitor plugin proxies are thenable; never resolve a Promise with them.
    // Wrap needed methods in a plain object to avoid triggering NativeBiometric.then().
    cachedNativeBiometric = {
      isAvailable: (options?: any) => plugin.isAvailable(options),
      verifyIdentity: (options?: any) => plugin.verifyIdentity(options),
      setCredentials: (options: any) => plugin.setCredentials(options),
      getCredentials: (options: any) => plugin.getCredentials(options),
      deleteCredentials: (options: any) => plugin.deleteCredentials(options),
      isCredentialsSaved: (options: any) => plugin.isCredentialsSaved(options),
      getPluginVersion: () => plugin.getPluginVersion(),
    }

    return cachedNativeBiometric
  } catch {
    cachedNativeBiometric = null
    return null
  }
}

export async function checkBiometricAvailability(): Promise<BiometricAvailability> {
  try {
    const NativeBiometric = await getNativeBiometric()
    if (!NativeBiometric) {
      return { isAvailable: false, biometricType: BiometricType.NONE }
    }

    const result = await NativeBiometric.isAvailable({ useFallback: true })

    if (!result.isAvailable) {
      return {
        isAvailable: false,
        biometricType: BiometricType.NONE,
        errorMessage: result.errorCode?.toString(),
      }
    }

    let biometricType: BiometricType
    switch (result.biometryType) {
      case 1: // TOUCH_ID (iOS)
      case 3: // FINGERPRINT (Android)
        biometricType = BiometricType.FINGERPRINT
        break
      case 2: // FACE_ID (iOS)
      case 4: // FACE_AUTHENTICATION (Android)
        biometricType = BiometricType.FACE
        break
      case 6: // MULTIPLE
        biometricType = BiometricType.MULTIPLE
        break
      default:
        biometricType = BiometricType.FINGERPRINT
    }

    return { isAvailable: true, biometricType }
  } catch {
    return { isAvailable: false, biometricType: BiometricType.NONE }
  }
}

export async function authenticateWithBiometric(
  reason: string,
): Promise<boolean> {
  try {
    const NativeBiometric = await getNativeBiometric()
    if (!NativeBiometric) return false

    await NativeBiometric.verifyIdentity({
      reason,
      title: "Finanze",
      maxAttempts: 3,
      useFallback: true,
    })
    return true
  } catch {
    return false
  }
}

export async function saveCredentials(
  credentials: BiometricCredentials,
): Promise<boolean> {
  try {
    const NativeBiometric = await getNativeBiometric()
    if (!NativeBiometric) return false

    await NativeBiometric.setCredentials({
      username: credentials.username,
      password: credentials.password,
      server: BIOMETRIC_SERVER,
    })
    return true
  } catch {
    return false
  }
}

export async function getCredentials(): Promise<BiometricCredentials | null> {
  try {
    const NativeBiometric = await getNativeBiometric()
    if (!NativeBiometric) return null

    const credentials = await NativeBiometric.getCredentials({
      server: BIOMETRIC_SERVER,
    })

    if (credentials.username && credentials.password) {
      return {
        username: credentials.username,
        password: credentials.password,
      }
    }
    return null
  } catch {
    return null
  }
}

export async function deleteCredentials(): Promise<boolean> {
  try {
    const NativeBiometric = await getNativeBiometric()
    if (!NativeBiometric) return false

    await NativeBiometric.deleteCredentials({
      server: BIOMETRIC_SERVER,
    })
    return true
  } catch {
    return false
  }
}

export async function hasStoredCredentials(): Promise<boolean> {
  try {
    const NativeBiometric = await getNativeBiometric()
    if (!NativeBiometric) return false

    const result = await NativeBiometric.isCredentialsSaved({
      server: BIOMETRIC_SERVER,
    })
    return result.isSaved
  } catch {
    return false
  }
}
