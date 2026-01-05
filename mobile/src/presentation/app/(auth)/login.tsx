import React, { useEffect, useMemo, useRef, useState } from "react"
import {
  View,
  Text,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  Keyboard,
  Animated,
  Easing,
  ActivityIndicator,
  Image,
} from "react-native"
import { SafeAreaView } from "react-native-safe-area-context"
import * as WebBrowser from "expo-web-browser"
import Svg, { Path } from "react-native-svg"
import { useAuth } from "@/presentation/context"
import { useTheme } from "@/presentation/context"
import { useI18n } from "@/presentation/i18n"
import { Button, TextInput } from "@/presentation/components/ui"
import { getThemeColors, typography, spacing } from "@/presentation/theme"
import {
  LOCKUP_LIFT_FROM_CENTER,
  LOGIN_FORM_SHIFT_DOWN,
} from "@/presentation/constants/logoLockup"

import splashIconDark from "../../../../assets/splash-icon.png"
import splashIconLight from "../../../../assets/splash-icon-light.png"

const TERMS_URL = "https://finanze.me/terms"
const PRIVACY_URL = "https://finanze.me/privacy"

const GoogleIcon = ({ color }: { color: string }) => (
  <Svg width={18} height={18} viewBox="0 0 24 24">
    <Path
      fill={color}
      d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z"
    />
    <Path
      fill={color}
      d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"
    />
    <Path
      fill={color}
      d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"
    />
    <Path
      fill={color}
      d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"
    />
  </Svg>
)

export default function LoginScreen() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { t, locale } = useI18n()
  const { signInWithEmail, signInWithGoogle, isLoading, error, clearError } =
    useAuth()
  const splashIcon = resolvedTheme === "dark" ? splashIconDark : splashIconLight

  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [localError, setLocalError] = useState<string | null>(null)
  const [showSuccessTransition, setShowSuccessTransition] = useState(false)

  const [lockupRowHeight, setLockupRowHeight] = useState(56)

  const logoTranslateY = useRef(new Animated.Value(-40)).current
  const logoOpacity = useRef(new Animated.Value(0)).current

  useEffect(() => {
    if (!showSuccessTransition) return

    // Start exactly where the login lockup is (no teleport), then move to center.
    logoOpacity.setValue(1)
    logoTranslateY.setValue(LOCKUP_LIFT_FROM_CENTER - lockupRowHeight / 2)

    Animated.timing(logoTranslateY, {
      toValue: -lockupRowHeight / 2,
      duration: 380,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: true,
    }).start()
  }, [lockupRowHeight, logoOpacity, logoTranslateY, showSuccessTransition])

  const handleEmailSignIn = async () => {
    if (!email.trim() || !password.trim()) {
      setLocalError(t.auth.emailRequired)
      return
    }

    setLocalError(null)
    clearError()

    try {
      Keyboard.dismiss()
      await signInWithEmail(email, password)
      setShowSuccessTransition(true)
    } catch (err: any) {
      console.error("Sign in error:", err)
    }
  }

  const handleGoogleSignIn = async () => {
    setLocalError(null)
    clearError()

    try {
      Keyboard.dismiss()
      await signInWithGoogle()
      setShowSuccessTransition(true)
    } catch (err: any) {
      console.error("Google sign in error:", err)
    }
  }

  const displayError = localError || error

  const showLoadingTransition = useMemo(() => {
    if (showSuccessTransition) return true
    return false
  }, [showSuccessTransition])

  const openExternalUrl = async (url: string) => {
    try {
      await WebBrowser.openBrowserAsync(url)
    } catch {
      // ignore
    }
  }

  const termsLabel = locale?.startsWith("es")
    ? "Términos de Servicio"
    : "Terms of Service"
  const privacyLabel = locale?.startsWith("es")
    ? "Política de Privacidad"
    : "Privacy Policy"

  const notice = t.auth.termsNotice
  const termsIndex = notice.indexOf(termsLabel)
  const privacyIndex = notice.indexOf(privacyLabel)
  const canSplit =
    termsIndex >= 0 && privacyIndex >= 0 && termsIndex < privacyIndex
  const prefix = canSplit ? notice.slice(0, termsIndex) : notice
  const between = canSplit
    ? notice.slice(termsIndex + termsLabel.length, privacyIndex)
    : " "
  const suffix = canSplit
    ? notice.slice(privacyIndex + privacyLabel.length)
    : ""

  if (showLoadingTransition) {
    return (
      <SafeAreaView
        edges={["left", "right"]}
        style={[styles.container, { backgroundColor: colors.background }]}
      >
        <Animated.View
          style={[
            styles.absoluteSuccess,
            {
              opacity: logoOpacity,
              transform: [{ translateY: logoTranslateY }],
            },
          ]}
        >
          <View
            style={styles.headerLockup}
            onLayout={event => {
              const nextHeight = event.nativeEvent.layout.height
              if (!nextHeight) return
              setLockupRowHeight(nextHeight)
            }}
          >
            <Image source={splashIcon} style={styles.headerLogoImage} />
            <Text style={[styles.logo, { color: colors.text }]}>Finanze</Text>
          </View>
          <ActivityIndicator size="small" color={colors.textMuted} />
        </Animated.View>
      </SafeAreaView>
    )
  }

  return (
    <SafeAreaView
      edges={["left", "right"]}
      style={[styles.container, { backgroundColor: colors.background }]}
    >
      <KeyboardAvoidingView
        behavior={Platform.OS === "ios" ? "padding" : "height"}
        style={styles.keyboardView}
      >
        {/*
          Absolute lockup positioned relative to the KeyboardAvoidingView.
          This makes it move up by the same amount as the form when the keyboard opens.
        */}
        <View
          pointerEvents="none"
          style={[
            styles.absoluteHeader,
            {
              transform: [
                {
                  translateY: LOCKUP_LIFT_FROM_CENTER - lockupRowHeight / 2,
                },
              ],
            },
          ]}
        >
          <View
            style={styles.headerLockup}
            onLayout={event => {
              const nextHeight = event.nativeEvent.layout.height
              if (!nextHeight) return
              setLockupRowHeight(nextHeight)
            }}
          >
            <Image source={splashIcon} style={styles.headerLogoImage} />
            <Text style={[styles.logo, { color: colors.text }]}>Finanze</Text>
          </View>
          <Text style={[styles.subtitle, { color: colors.textSecondary }]}>
            {t.onboarding.welcomeSubtitle}
          </Text>
        </View>

        <View
          style={[
            styles.content,
            { transform: [{ translateY: LOGIN_FORM_SHIFT_DOWN }] },
          ]}
        >
          {/* Login Form */}
          <View style={styles.form}>
            <TextInput
              label={t.auth.email}
              placeholder={t.auth.emailPlaceholder}
              value={email}
              onChangeText={text => {
                setEmail(text)
                setLocalError(null)
              }}
              keyboardType="email-address"
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              autoComplete="email"
              editable={!isLoading}
            />

            <TextInput
              label={t.auth.password}
              placeholder={t.auth.passwordPlaceholder}
              value={password}
              onChangeText={text => {
                setPassword(text)
                setLocalError(null)
              }}
              secureTextEntry
              autoCapitalize="none"
              autoCorrect={false}
              spellCheck={false}
              autoComplete="password"
              editable={!isLoading}
            />

            {displayError && (
              <Text style={[styles.errorInline, { color: colors.danger[600] }]}>
                {displayError}
              </Text>
            )}

            <Button
              title={t.auth.signIn}
              onPress={handleEmailSignIn}
              loading={isLoading}
              disabled={isLoading}
            />
          </View>

          {/* Divider */}
          <View style={styles.divider}>
            <View
              style={[styles.dividerLine, { backgroundColor: colors.border }]}
            />
            <Text style={[styles.dividerText, { color: colors.textMuted }]}>
              {t.auth.orContinueWith}
            </Text>
            <View
              style={[styles.dividerLine, { backgroundColor: colors.border }]}
            />
          </View>

          {/* Google Sign In */}
          <Button
            title={t.auth.signInWithGoogle}
            onPress={handleGoogleSignIn}
            variant="outline"
            loading={isLoading}
            disabled={isLoading}
            icon={<GoogleIcon color={colors.text} />}
          />

          {/* Footer */}
          <View style={styles.footer}>
            <Text style={[styles.footerText, { color: colors.textMuted }]}>
              {prefix}
              <Text
                style={[
                  styles.footerLink,
                  { color: colors.text, textDecorationColor: colors.text },
                ]}
                onPress={() => openExternalUrl(TERMS_URL)}
              >
                {termsLabel}
              </Text>
              {between}
              <Text
                style={[
                  styles.footerLink,
                  { color: colors.text, textDecorationColor: colors.text },
                ]}
                onPress={() => openExternalUrl(PRIVACY_URL)}
              >
                {privacyLabel}
              </Text>
              {suffix}
            </Text>
          </View>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  )
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
  },
  absoluteSuccess: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    gap: spacing.lg,
  },
  keyboardView: {
    flex: 1,
  },
  content: {
    flex: 1,
    padding: spacing.xl,
    justifyContent: "center",
  },
  absoluteHeader: {
    position: "absolute",
    top: "50%",
    left: 0,
    right: 0,
    alignItems: "center",
    zIndex: 1,
  },
  headerLockup: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
  },
  headerLogoImage: {
    width: 56,
    height: 56,
    marginRight: 12,
  },
  logo: {
    fontSize: 42,
    fontWeight: "700",
    letterSpacing: -1,
  },
  subtitle: {
    ...typography.body,
    marginTop: spacing.sm,
  },
  form: {
    gap: spacing.lg,
  },
  errorInline: {
    ...typography.bodySmall,
    textAlign: "center",
  },
  divider: {
    flexDirection: "row",
    alignItems: "center",
    marginVertical: spacing.xl,
  },
  dividerLine: {
    flex: 1,
    height: 1,
  },
  dividerText: {
    ...typography.bodySmall,
    marginHorizontal: spacing.md,
  },
  footer: {
    marginTop: spacing.xxxl,
    alignItems: "center",
  },
  footerText: {
    ...typography.bodySmall,
    textAlign: "center",
    lineHeight: 18,
  },
  footerLink: {
    textDecorationLine: "underline",
    textDecorationStyle: "solid",
  },
})
