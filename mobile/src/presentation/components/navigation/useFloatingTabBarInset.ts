import { useSafeAreaInsets } from "react-native-safe-area-context"
import { spacing } from "@/presentation/theme"

// Keep in sync with the floating pill heights in FloatingTabBar.
const FLOATING_TAB_BAR_MAX_HEIGHT = 50

export function useFloatingTabBarContentInset() {
  const insets = useSafeAreaInsets()

  // The tab bar itself sits above the bottom and includes extra padding.
  const bottomSafe = insets.bottom > 0 ? insets.bottom : spacing.lg

  // Extra breathing room so the last content isn't tight against the pill.
  return FLOATING_TAB_BAR_MAX_HEIGHT + bottomSafe + spacing.lg
}
