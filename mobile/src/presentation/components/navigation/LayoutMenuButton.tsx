import React from "react"
import {
  Animated,
  Easing,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native"
import { BlurView } from "expo-blur"
import { router, usePathname, type Href } from "expo-router"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { useTheme } from "@/presentation/context"
import {
  borderRadius,
  getThemeColors,
  spacing,
  typography,
} from "@/presentation/theme"
import {
  ArrowLeftRight,
  LayoutDashboard,
  Settings,
  EllipsisVertical,
} from "lucide-react-native"

const BUTTON_SIZE = 40
const PANEL_WIDTH = 240

type LayoutMenuButtonProps = {
  anchorTop?: number
  onNavigate?: () => void
}

type MenuItem = {
  label: string
  icon: React.ComponentType<{ size?: number; color?: string }>
  href: Href
  onPress: () => void
}

function normalizeRoute(input: unknown): string {
  let path = String(input ?? "/")

  // expo-router pathnames do not include group names like "(tabs)", but hrefs might.
  path = path.replace("/(tabs)", "")
  path = path.replace("/(tabs)/", "/")

  // Normalize trailing index routes.
  path = path.replace(/\/index$/, "/")

  // Ensure a consistent root.
  if (path.length === 0) return "/"

  return path
}

function isSameRoute(a: unknown, b: unknown): boolean {
  return normalizeRoute(a) === normalizeRoute(b)
}

function GlassSurface({
  children,
  colors,
  tint,
  style,
}: {
  children: React.ReactNode
  colors: ReturnType<typeof getThemeColors>
  tint: "light" | "dark"
  style?: object
}) {
  return (
    <View
      style={[
        styles.glassBase,
        {
          borderColor: colors.border,
        },
        style,
      ]}
    >
      <BlurView
        tint={tint}
        intensity={70}
        style={StyleSheet.absoluteFillObject}
      />
      <View
        style={[
          StyleSheet.absoluteFillObject,
          {
            backgroundColor:
              tint === "dark"
                ? "rgba(0, 0, 0, 0.3)"
                : "rgba(248, 248, 248, 0.5)",
          },
        ]}
      />
      <View style={styles.glassContent}>{children}</View>
    </View>
  )
}

export function LayoutMenuButton({
  anchorTop,
  onNavigate,
}: LayoutMenuButtonProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const insets = useSafeAreaInsets()
  const pathname = usePathname()
  const [open, setOpen] = React.useState(false)
  const [visible, setVisible] = React.useState(false)
  const progress = React.useRef(new Animated.Value(0)).current

  const tint = resolvedTheme === "dark" ? "dark" : "light"

  const closeMenu = React.useCallback(() => {
    Animated.timing(progress, {
      toValue: 0,
      duration: 220,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: true,
    }).start(({ finished }) => {
      if (finished) {
        setVisible(false)
        setOpen(false)
      }
    })
  }, [progress])

  const openMenu = React.useCallback(() => {
    setOpen(true)
    setVisible(true)
    progress.setValue(0)
    Animated.timing(progress, {
      toValue: 1,
      duration: 240,
      easing: Easing.inOut(Easing.cubic),
      useNativeDriver: true,
    }).start()
  }, [progress])

  const navigateIfNeeded = React.useCallback(
    (href: Href, mode: "replace" | "push") => {
      onNavigate?.()

      if (isSameRoute(pathname || "/", href)) {
        closeMenu()
        return
      }

      closeMenu()
      if (mode === "replace") router.replace(href)
      else router.push(href)
    },
    [closeMenu, onNavigate, pathname],
  )

  const items: MenuItem[] = React.useMemo(
    () => [
      {
        label: "Dashboard",
        icon: LayoutDashboard,
        href: "/(tabs)/dashboard",
        onPress: () => navigateIfNeeded("/(tabs)/dashboard" as Href, "replace"),
      },
      {
        label: "Transactions",
        icon: ArrowLeftRight,
        href: "/(tabs)/transactions",
        onPress: () => navigateIfNeeded("/(tabs)/transactions" as Href, "push"),
      },
      {
        label: "Settings",
        icon: Settings,
        href: "/(tabs)/settings",
        onPress: () => navigateIfNeeded("/(tabs)/settings" as Href, "push"),
      },
    ],
    [navigateIfNeeded],
  )

  // Get the current menu item's icon based on pathname
  const currentMenuItem = React.useMemo(() => {
    return items.find(item => isSameRoute(pathname || "/", item.href))
  }, [items, pathname])

  const buttonIcon = currentMenuItem?.icon || EllipsisVertical

  const baseTop = anchorTop ?? insets.top + spacing.md
  const panelTop = baseTop

  const itemHeight = spacing.md * 2 + 20
  const panelHeight = spacing.sm * 2 + items.length * itemHeight
  const scaleStart = BUTTON_SIZE / PANEL_WIDTH
  const translateXStart = (-PANEL_WIDTH * (1 - scaleStart)) / 2
  const translateYStart = (-panelHeight * (1 - scaleStart)) / 2

  const backdropOpacity = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [0, 1],
  })

  const panelOpacity = progress
  const panelScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [scaleStart, 1],
  })
  const panelTranslateX = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [translateXStart, 0],
  })
  const panelTranslateY = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [translateYStart, 0],
  })

  const buttonOpacity = progress.interpolate({
    inputRange: [0, 0.22, 1],
    outputRange: [1, 0, 0],
  })
  const buttonScale = progress.interpolate({
    inputRange: [0, 1],
    outputRange: [1, 0.75],
  })

  const iconColor = colors.text

  return (
    <>
      <Pressable
        onPress={openMenu}
        hitSlop={12}
        accessibilityRole="button"
        accessibilityLabel="Open navigation menu"
        disabled={open}
      >
        <Animated.View
          pointerEvents={open ? "none" : "auto"}
          style={{
            opacity: buttonOpacity,
            transform: [{ scale: buttonScale }],
          }}
        >
          <GlassSurface
            colors={colors}
            tint={tint}
            style={styles.buttonSurface}
          >
            <View style={styles.buttonInner}>
              {React.createElement(buttonIcon, {
                size: 18,
                color: iconColor,
              })}
            </View>
          </GlassSurface>
        </Animated.View>
      </Pressable>

      <Modal
        visible={open}
        transparent
        animationType="none"
        onRequestClose={closeMenu}
      >
        {visible ? (
          <View style={styles.modalRoot}>
            <Animated.View
              style={[styles.backdrop, { opacity: backdropOpacity }]}
            >
              <Pressable
                style={StyleSheet.absoluteFillObject}
                onPress={closeMenu}
                accessibilityRole="button"
                accessibilityLabel="Close navigation menu"
              />
            </Animated.View>

            <Animated.View
              style={[
                styles.panelWrapper,
                {
                  top: panelTop,
                  left: spacing.md,
                  opacity: panelOpacity,
                  transform: [
                    { scale: panelScale },
                    { translateX: panelTranslateX },
                    { translateY: panelTranslateY },
                  ],
                },
              ]}
            >
              <GlassSurface
                colors={colors}
                tint={tint}
                style={styles.panelSurface}
              >
                {items.map((item, idx) => (
                  <Pressable
                    key={item.label}
                    onPress={item.onPress}
                    style={({ pressed }) => [
                      styles.item,
                      {
                        borderColor: colors.border,
                        borderTopWidth:
                          idx === 0 ? 0 : StyleSheet.hairlineWidth,
                        opacity: pressed ? 0.7 : 1,
                      },
                    ]}
                    accessibilityRole="button"
                  >
                    <item.icon size={18} color={iconColor} />
                    <Text style={[styles.itemText, { color: iconColor }]}>
                      {item.label}
                    </Text>
                  </Pressable>
                ))}
              </GlassSurface>
            </Animated.View>
          </View>
        ) : null}
      </Modal>
    </>
  )
}

const styles = StyleSheet.create({
  glassBase: {
    borderRadius: borderRadius.full,
    borderWidth: 1,
    overflow: "hidden",
  },
  glassContent: {
    flex: 1,
  },
  buttonSurface: {
    width: BUTTON_SIZE,
    height: BUTTON_SIZE,
  },
  buttonInner: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
  },
  modalRoot: {
    flex: 1,
  },
  backdrop: {
    ...StyleSheet.absoluteFillObject,
    backgroundColor: "transparent",
  },
  panelWrapper: {
    position: "absolute",
  },
  panelSurface: {
    borderRadius: borderRadius.xl,
    paddingVertical: spacing.sm,
    minWidth: 200,
  },
  item: {
    flexDirection: "row",
    alignItems: "center",
    gap: spacing.md,
    paddingVertical: spacing.md,
    paddingHorizontal: spacing.lg,
  },
  itemText: {
    ...typography.bodyLarge,
    fontWeight: "400",
  },
})
