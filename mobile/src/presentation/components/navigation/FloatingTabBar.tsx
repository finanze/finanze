import React from "react"
import { View, Pressable, StyleSheet, LayoutChangeEvent } from "react-native"
import Animated, {
  interpolate,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
  withSpring,
} from "react-native-reanimated"
import { useSafeAreaInsets } from "react-native-safe-area-context"
import { BlurView } from "expo-blur"
import type { BottomTabBarProps } from "@react-navigation/bottom-tabs"
import { useTheme } from "@/presentation/context"
import { useLayoutMenuScroll } from "@/presentation/context"
import { getThemeColors, spacing, borderRadius } from "@/presentation/theme"

const PILL_HEIGHT = 50
const PILL_HEIGHT_COLLAPSED = 32
const INDICATOR_INSET = spacing.xs
const COLLAPSE_DURATION_MS = 180
const DOT_SIZE = 6
const DOT_GAP = 6
const DOT_PADDING_H = spacing.sm
const SPRING_CONFIG = {
  damping: 18,
  stiffness: 200,
  mass: 0.8,
}

export function FloatingTabBar({
  state,
  descriptors,
  navigation,
}: BottomTabBarProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const insets = useSafeAreaInsets()
  const tint = resolvedTheme === "dark" ? "dark" : "light"
  const { scrolling, atTop, atBottom } = useLayoutMenuScroll()

  const [collapsed, setCollapsed] = React.useState(false)

  React.useEffect(() => {
    if (scrolling) setCollapsed(true)
  }, [scrolling])

  React.useEffect(() => {
    // Only expand automatically after scrolling has stopped
    // and the user is at the very top or bottom.
    if (!scrolling && (atTop || atBottom)) setCollapsed(false)
  }, [atBottom, atTop, scrolling])

  const collapse = useSharedValue(0)
  const expandedWidth = useSharedValue(0)
  const collapsedWidth = useSharedValue(PILL_HEIGHT)

  // Track tab positions for the sliding indicator (route.key -> layout)
  const layoutByKeyRef = React.useRef<
    Record<string, { x: number; width: number }>
  >({})
  const indicatorX = useSharedValue(0)
  const indicatorWidth = useSharedValue(0)

  const updateIndicatorForKey = React.useCallback(
    (routeKey: string) => {
      const layout = layoutByKeyRef.current[routeKey]
      if (!layout) return

      indicatorX.value = withSpring(layout.x, SPRING_CONFIG)
      indicatorWidth.value = withSpring(layout.width, SPRING_CONFIG)
    },
    [indicatorWidth, indicatorX],
  )

  const handleTabLayout = (routeKey: string) => (event: LayoutChangeEvent) => {
    const { width, x } = event.nativeEvent.layout
    layoutByKeyRef.current[routeKey] = { x, width }

    // If this is the active route, update immediately.
    if (state.routes[state.index]?.key === routeKey) {
      updateIndicatorForKey(routeKey)
    }

    // Once we have all visible tab widths, compute the expanded pill width.
    // This prevents clipping when adding more tabs.
    const visibleKeys = state.routes
      .filter(r => r.name !== "index")
      .map(r => r.key)
    const hasAll = visibleKeys.every(
      k => (layoutByKeyRef.current[k]?.width ?? 0) > 0,
    )
    if (hasAll) {
      const total = visibleKeys.reduce(
        (acc, k) => acc + (layoutByKeyRef.current[k]?.width ?? 0),
        0,
      )
      // Account for the tabsRow horizontal padding.
      expandedWidth.value = withSpring(total + spacing.xs * 2, SPRING_CONFIG)
    }
  }

  // Update indicator when active tab changes
  React.useEffect(() => {
    const activeKey = state.routes[state.index]?.key
    if (!activeKey) return
    updateIndicatorForKey(activeKey)
  }, [state.index, state.routes, updateIndicatorForKey])

  React.useEffect(() => {
    collapse.value = withTiming(collapsed ? 1 : 0, {
      duration: COLLAPSE_DURATION_MS,
    })
  }, [collapse, collapsed])

  const indicatorStyle = useAnimatedStyle(() => ({
    transform: [{ translateX: indicatorX.value }],
    width: indicatorWidth.value,
    opacity: interpolate(collapse.value, [0, 1], [1, 0]),
  }))

  // Keep tab bar minimal: hide only the redirect route.
  const visibleRoutes = state.routes.filter(route => route.name !== "index")

  const activeKey = state.routes[state.index]?.key
  const activeVisibleIndex = Math.max(
    0,
    visibleRoutes.findIndex(r => r.key === activeKey),
  )

  React.useEffect(() => {
    const w =
      DOT_PADDING_H * 2 +
      visibleRoutes.length * DOT_SIZE +
      (visibleRoutes.length - 1) * DOT_GAP
    collapsedWidth.value = Math.max(PILL_HEIGHT_COLLAPSED, w)
  }, [collapsedWidth, visibleRoutes.length])

  const pillAnimatedStyle = useAnimatedStyle(() => {
    const w = expandedWidth.value
    if (w <= 0) return {}
    return {
      width: interpolate(collapse.value, [0, 1], [w, collapsedWidth.value]),
      height: interpolate(
        collapse.value,
        [0, 1],
        [PILL_HEIGHT, PILL_HEIGHT_COLLAPSED],
      ),
    }
  })

  const tabsRowAnimatedStyle = useAnimatedStyle(() => ({
    opacity: interpolate(collapse.value, [0, 1], [1, 0]),
    transform: [{ scale: interpolate(collapse.value, [0, 1], [1, 0.85]) }],
  }))

  const dotAnimatedStyle = useAnimatedStyle(() => ({
    opacity: interpolate(collapse.value, [0, 1], [0, 1]),
    transform: [{ scale: interpolate(collapse.value, [0, 1], [0.85, 1]) }],
  }))

  const handlePillPress = () => {
    if (!collapsed) return
    setCollapsed(false)
  }

  return (
    <View
      style={[
        styles.container,
        { paddingBottom: insets.bottom > 0 ? insets.bottom : spacing.lg },
      ]}
      pointerEvents="box-none"
    >
      <View style={styles.pillWrapper}>
        <Pressable
          onPress={handlePillPress}
          disabled={!collapsed}
          accessibilityRole="button"
          accessibilityLabel="Open navigation"
        >
          <Animated.View
            style={[
              styles.pillBase,
              { borderColor: colors.border },
              pillAnimatedStyle,
            ]}
          >
            <BlurView
              tint={tint}
              intensity={80}
              style={StyleSheet.absoluteFillObject}
            />
            <View
              style={[
                StyleSheet.absoluteFillObject,
                {
                  backgroundColor: colors.surface,
                },
              ]}
            />

            {/* Collapsed dot content */}
            <Animated.View
              pointerEvents="none"
              style={[styles.dotRow, dotAnimatedStyle]}
            >
              {visibleRoutes.map((r, idx) => {
                const isActive = idx === activeVisibleIndex
                return (
                  <View
                    key={r.key}
                    style={[
                      styles.dot,
                      {
                        backgroundColor: isActive
                          ? colors.text
                          : colors.textMuted,
                        opacity: isActive ? 1 : 0.7,
                      },
                    ]}
                  />
                )
              })}
            </Animated.View>

            {/* Tab buttons + sliding indicator (same coordinate space) */}
            <Animated.View
              style={[styles.tabsRow, tabsRowAnimatedStyle]}
              pointerEvents={collapsed ? "none" : "auto"}
            >
              <Animated.View
                pointerEvents="none"
                style={[
                  styles.indicator,
                  {
                    backgroundColor: colors.surfaceElevated,
                    borderColor: colors.border,
                  },
                  indicatorStyle,
                ]}
              />
              {visibleRoutes.map(route => {
                const routeIndex = state.routes.findIndex(
                  r => r.key === route.key,
                )
                const { options } = descriptors[route.key]
                const isFocused = state.index === routeIndex

                const onPress = () => {
                  const event = navigation.emit({
                    type: "tabPress",
                    target: route.key,
                    canPreventDefault: true,
                  })

                  if (!isFocused && !event.defaultPrevented) {
                    navigation.navigate(route.name, route.params)
                  }
                }

                const onLongPress = () => {
                  navigation.emit({
                    type: "tabLongPress",
                    target: route.key,
                  })
                }

                const iconColor = isFocused ? colors.text : colors.textMuted

                return (
                  <Pressable
                    key={route.key}
                    accessibilityRole="button"
                    accessibilityState={isFocused ? { selected: true } : {}}
                    accessibilityLabel={options.tabBarAccessibilityLabel}
                    onPress={onPress}
                    onLongPress={onLongPress}
                    onLayout={handleTabLayout(route.key)}
                    style={styles.tab}
                  >
                    {options.tabBarIcon?.({
                      focused: isFocused,
                      color: iconColor,
                      size: 22,
                    })}
                  </Pressable>
                )
              })}
            </Animated.View>
          </Animated.View>
        </Pressable>
      </View>
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    position: "absolute",
    bottom: 0,
    left: 0,
    right: 0,
    alignItems: "center",
  },
  pillWrapper: {
    alignItems: "center",
  },
  pillBase: {
    flexDirection: "row",
    borderRadius: borderRadius.full,
    borderWidth: 1,
    overflow: "hidden",
    position: "relative",
    height: PILL_HEIGHT,
    justifyContent: "center",
    minWidth: PILL_HEIGHT_COLLAPSED,
  },
  dotRow: {
    position: "absolute",
    left: 0,
    right: 0,
    top: 0,
    bottom: 0,
    alignItems: "center",
    justifyContent: "center",
    flexDirection: "row",
    paddingHorizontal: DOT_PADDING_H,
    gap: DOT_GAP,
  },
  dot: {
    width: DOT_SIZE,
    height: DOT_SIZE,
    borderRadius: borderRadius.full,
  },
  indicator: {
    position: "absolute",
    top: INDICATOR_INSET,
    bottom: INDICATOR_INSET,
    left: 0,
    borderRadius: borderRadius.full,
    borderWidth: StyleSheet.hairlineWidth,
  },
  tabsRow: {
    flexDirection: "row",
    alignItems: "center",
    height: "100%",
    position: "relative",
    paddingHorizontal: spacing.xs,
  },
  tab: {
    paddingHorizontal: spacing.lg,
    height: "100%",
    alignItems: "center",
    justifyContent: "center",
    zIndex: 1,
  },
})
