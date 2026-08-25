export interface SmsReceivedEvent {
  message: string
}

interface SmsOtpListenerHandle {
  remove: () => Promise<void>
}

interface SmsOtpPlugin {
  startListening(): Promise<void>
  stopListening(): Promise<void>
  addListener(
    eventName: "smsReceived",
    listenerFunc: (event: SmsReceivedEvent) => void,
  ): Promise<SmsOtpListenerHandle>
}

let cachedSmsOtp: SmsOtpPlugin | null | undefined
let lastSmsMessage: string | null = null

export function getLastSmsOtpMessage(): string | null {
  return lastSmsMessage
}

async function getSmsOtp(): Promise<SmsOtpPlugin | null> {
  if (!__MOBILE__) return null
  if (cachedSmsOtp !== undefined) return cachedSmsOtp

  try {
    const { Capacitor, registerPlugin } = await import("@capacitor/core")
    if (Capacitor.getPlatform() !== "android") {
      cachedSmsOtp = null
      return null
    }
    const plugin = registerPlugin<SmsOtpPlugin>("SmsOtp")
    cachedSmsOtp = {
      startListening: () => plugin.startListening(),
      stopListening: () => plugin.stopListening(),
      addListener: async (eventName, listenerFunc) => {
        const handle = await plugin.addListener(eventName, event => {
          if (event?.message) lastSmsMessage = event.message
          listenerFunc(event)
        })
        if (lastSmsMessage) {
          listenerFunc({ message: lastSmsMessage })
        }
        return handle
      },
    }
    return cachedSmsOtp
  } catch {
    cachedSmsOtp = null
    return null
  }
}

export async function startSmsOtpListening(): Promise<boolean> {
  const plugin = await getSmsOtp()
  if (!plugin) return false
  try {
    await plugin.startListening()
    return true
  } catch {
    return false
  }
}

export async function stopSmsOtpListening(): Promise<void> {
  lastSmsMessage = null
  const plugin = await getSmsOtp()
  try {
    await plugin?.stopListening()
  } catch {
    // Consent timeout / already stopped is expected.
  }
}

export async function addSmsOtpReceivedListener(
  listenerFunc: (event: SmsReceivedEvent) => void,
): Promise<SmsOtpListenerHandle | null> {
  const plugin = await getSmsOtp()
  if (!plugin) return null
  return plugin.addListener("smsReceived", listenerFunc)
}
