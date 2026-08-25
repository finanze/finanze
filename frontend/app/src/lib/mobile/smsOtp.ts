export interface SmsReceivedEvent {
  message: string
}

export interface SmsOtpListenerHandle {
  remove: () => Promise<void>
}

export async function startSmsOtpListening(): Promise<boolean> {
  if (!__MOBILE__) return false
  const { startSmsOtpListening: startListening } =
    await import("@/lib/capacitor/smsOtp")
  return startListening()
}

export async function stopSmsOtpListening(): Promise<void> {
  if (!__MOBILE__) return
  const { stopSmsOtpListening: stopListening } =
    await import("@/lib/capacitor/smsOtp")
  await stopListening()
}

export async function addSmsOtpReceivedListener(
  listenerFunc: (event: SmsReceivedEvent) => void,
): Promise<SmsOtpListenerHandle | null> {
  if (!__MOBILE__) return null
  const { addSmsOtpReceivedListener: addListener } =
    await import("@/lib/capacitor/smsOtp")
  return addListener(listenerFunc)
}

export async function getLastSmsOtpMessage(): Promise<string | null> {
  if (!__MOBILE__) return null
  const { getLastSmsOtpMessage: getLastMessage } =
    await import("@/lib/capacitor/smsOtp")
  return getLastMessage()
}
