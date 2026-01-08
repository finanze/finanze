import React, { useState } from "react"
import {
  TextInput as RNTextInput,
  View,
  Text,
  StyleSheet,
  TextInputProps as RNTextInputProps,
} from "react-native"
import { useTheme } from "../../context/ThemeContext"
import { getThemeColors, typography, borderRadius, spacing } from "../../theme"

interface TextInputProps extends RNTextInputProps {
  label?: string
  error?: string
  leftIcon?: React.ReactNode
  rightIcon?: React.ReactNode
}

export function TextInput({
  label,
  error,
  leftIcon,
  rightIcon,
  style,
  ...props
}: TextInputProps) {
  const { resolvedTheme: colorScheme } = useTheme()
  const colors = getThemeColors(colorScheme)
  const [isFocused, setIsFocused] = useState(false)

  const getBorderColor = () => {
    if (error) return colors.danger[500]
    if (isFocused) return colors.text
    return colors.border
  }

  return (
    <View style={styles.container}>
      {label && (
        <Text style={[styles.label, { color: colors.textSecondary }]}>
          {label}
        </Text>
      )}
      <View
        style={[
          styles.inputContainer,
          {
            backgroundColor: colors.surface,
            borderColor: getBorderColor(),
          },
        ]}
      >
        {leftIcon && <View style={styles.iconLeft}>{leftIcon}</View>}
        <RNTextInput
          style={[
            styles.input,
            { color: colors.text },
            !!leftIcon && styles.inputWithLeftIcon,
            !!rightIcon && styles.inputWithRightIcon,
            style,
          ]}
          placeholderTextColor={colors.textMuted}
          selectionColor={colors.text}
          cursorColor={colors.text}
          onFocus={() => setIsFocused(true)}
          onBlur={() => setIsFocused(false)}
          {...props}
        />
        {rightIcon && <View style={styles.iconRight}>{rightIcon}</View>}
      </View>
      {error && (
        <Text style={[styles.error, { color: colors.danger[500] }]}>
          {error}
        </Text>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  container: {
    gap: spacing.xs,
  },
  label: {
    ...typography.label,
  },
  inputContainer: {
    flexDirection: "row",
    alignItems: "stretch",
    borderWidth: 1,
    borderRadius: borderRadius.xl,
    minHeight: 52,
  },
  input: {
    flex: 1,
    alignSelf: "stretch",
    paddingHorizontal: spacing.lg,
    paddingVertical: 0,
    ...typography.body,
    lineHeight: 18,
    textAlignVertical: "center",
    includeFontPadding: false,
  },
  inputWithLeftIcon: {
    paddingLeft: spacing.sm,
  },
  inputWithRightIcon: {
    paddingRight: spacing.sm,
  },
  iconLeft: {
    justifyContent: "center",
    paddingLeft: spacing.md,
  },
  iconRight: {
    justifyContent: "center",
    paddingRight: spacing.md,
  },
  error: {
    ...typography.bodySmall,
    marginTop: spacing.xs,
  },
})
