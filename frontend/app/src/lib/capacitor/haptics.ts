import { isIOS } from "@/lib/platform"
import { LightHaptics } from "./plugins"

export function prepareLightHaptic() {
  if (!isIOS()) return

  void LightHaptics.prepare().catch(error => {
    console.error("Failed to prepare haptic feedback:", error)
  })
}

export function triggerLightHaptic() {
  if (!isIOS()) return

  void LightHaptics.impact().catch(error => {
    console.error("Failed to trigger haptic feedback:", error)
  })
}
