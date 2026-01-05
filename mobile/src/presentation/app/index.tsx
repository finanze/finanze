import { useEffect, useRef, useState } from "react"
import {
  View,
  ActivityIndicator,
  Text,
  StyleSheet,
  Animated,
  Easing,
  Image,
} from "react-native"
import { Redirect, router } from "expo-router"
import { SafeAreaView } from "react-native-safe-area-context"
import { useAuth } from "@/presentation/context"
import { useTheme } from "@/presentation/context"
import { getThemeColors } from "@/presentation/theme"
import {
  LOCKUP_LIFT_FROM_CENTER,
  SPINNER_OFFSET_FROM_CENTER,
} from "@/presentation/constants/logoLockup"

import splashIconDark from "../../../assets/splash-icon.png"
import splashIconLight from "../../../assets/splash-icon-light.png"

export default function Index() {
  const { user, isInitialized } = useAuth()
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const splashIcon = resolvedTheme === "dark" ? splashIconDark : splashIconLight

  const [isTransitioningToLogin, setIsTransitioningToLogin] = useState(false)
  const [showTitle, setShowTitle] = useState(false)
  const [measuredTitleWidth, setMeasuredTitleWidth] = useState<number | null>(
    null,
  )

  const headerTranslateY = useRef(new Animated.Value(0)).current
  const lockupTranslateX = useRef(new Animated.Value(0)).current
  const titleOpacity = useRef(new Animated.Value(0)).current
  const titleTranslateX = useRef(new Animated.Value(28)).current
  const headerCenterOffsetY = useRef(new Animated.Value(-28)).current

  const AnimatedImage = useRef(Animated.createAnimatedComponent(Image)).current

  useEffect(() => {
    if (!isInitialized) return
    if (user) return
    if (isTransitioningToLogin) return
    if (measuredTitleWidth === null) return

    setIsTransitioningToLogin(true)

    // Keep the icon perfectly centered at the start, then reveal the title and
    // animate the lockup into place before moving it up into the login flow.
    setShowTitle(true)
    headerTranslateY.setValue(0)
    titleOpacity.setValue(0)
    titleTranslateX.setValue(28)

    const offset = (styles.loadingTitle.marginLeft + measuredTitleWidth) / 2
    lockupTranslateX.setValue(offset)

    Animated.sequence([
      Animated.delay(220),
      Animated.parallel([
        Animated.timing(lockupTranslateX, {
          toValue: 0,
          duration: 420,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(titleOpacity, {
          toValue: 1,
          duration: 280,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
        Animated.timing(titleTranslateX, {
          toValue: 0,
          duration: 420,
          easing: Easing.out(Easing.cubic),
          useNativeDriver: true,
        }),
      ]),
      Animated.timing(headerTranslateY, {
        toValue: LOCKUP_LIFT_FROM_CENTER,
        duration: 420,
        easing: Easing.out(Easing.cubic),
        useNativeDriver: true,
      }),
    ]).start(() => {
      router.replace("/(auth)/login")
    })
  }, [
    headerCenterOffsetY,
    headerTranslateY,
    isInitialized,
    isTransitioningToLogin,
    lockupTranslateX,
    measuredTitleWidth,
    titleOpacity,
    titleTranslateX,
    user,
  ])

  // Show centered splash while checking auth and onboarding state.
  // If the user is not authenticated, we keep this splash and slide the logo up into the login flow.
  if (!isInitialized || isTransitioningToLogin || !user) {
    return (
      <SafeAreaView
        edges={["left", "right"]}
        style={[
          styles.loadingContainer,
          { backgroundColor: colors.background },
        ]}
      >
        {/* Hidden title measurement so we can keep the icon perfectly centered at start. */}
        <Text
          style={[
            styles.loadingTitle,
            styles.titleMeasure,
            { color: colors.text },
          ]}
          onLayout={event => {
            if (measuredTitleWidth !== null) return
            setMeasuredTitleWidth(event.nativeEvent.layout.width)
          }}
        >
          Finanze
        </Text>

        <Animated.View
          style={[
            styles.header,
            {
              transform: [
                {
                  translateY: Animated.add(
                    headerTranslateY,
                    headerCenterOffsetY,
                  ),
                },
              ],
            },
          ]}
        >
          <Animated.View
            style={{ transform: [{ translateX: lockupTranslateX }] }}
          >
            <AnimatedImage
              source={splashIcon}
              style={styles.logoImage}
              resizeMode="contain"
            />
          </Animated.View>

          {showTitle ? (
            <Animated.Text
              style={[
                styles.loadingTitle,
                {
                  color: colors.text,
                  opacity: titleOpacity,
                  transform: [{ translateX: titleTranslateX }],
                },
              ]}
            >
              Finanze
            </Animated.Text>
          ) : null}
        </Animated.View>

        <View pointerEvents="none" style={styles.spinnerContainer}>
          <ActivityIndicator size="large" color={colors.textMuted} />
        </View>
      </SafeAreaView>
    )
  }

  // Logged in -> onboarding flow decides decrypt/no-backup/not-allowed
  return <Redirect href="/onboarding" />
}

const styles = StyleSheet.create({
  loadingContainer: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
  },
  header: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    minHeight: 56,
  },
  logoImage: {
    width: 56,
    height: 56,
  },
  loadingTitle: {
    fontSize: 42,
    fontWeight: "700",
    letterSpacing: -1,
    marginLeft: 12,
  },
  titleMeasure: {
    position: "absolute",
    opacity: 0,
    top: -9999,
    left: -9999,
  },
  spinnerContainer: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    transform: [{ translateY: SPINNER_OFFSET_FROM_CENTER }],
  },
})
