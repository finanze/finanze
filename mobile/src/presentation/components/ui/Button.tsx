import React from "react"
import {
  TouchableOpacity,
  Text,
  StyleSheet,
  ActivityIndicator,
  ViewStyle,
  TextStyle,
  StyleProp,
} from "react-native"
import { useTheme } from "../../context/ThemeContext"
import { getThemeColors, typography, borderRadius, spacing } from "../../theme"

interface ButtonProps {
  title: string
  onPress: () => void
  variant?: "primary" | "secondary" | "outline" | "ghost"
  size?: "sm" | "md" | "lg"
  disabled?: boolean
  loading?: boolean
  icon?: React.ReactNode
  style?: StyleProp<ViewStyle>
}

export function Button({
  title,
  onPress,
  variant = "primary",
  size = "md",
  disabled = false,
  loading = false,
  icon,
  style,
}: ButtonProps) {
  const { resolvedTheme: colorScheme } = useTheme()
  const colors = getThemeColors(colorScheme)

  const getButtonStyles = (): ViewStyle => {
    const baseStyle: ViewStyle = {
      flexDirection: "row",
      alignItems: "center",
      justifyContent: "center",
      borderRadius: borderRadius.lg,
      gap: spacing.sm,
    }

    // Size styles
    const sizeStyles: Record<string, ViewStyle> = {
      sm: {
        paddingHorizontal: spacing.md,
        paddingVertical: spacing.sm,
        minHeight: 36,
      },
      md: {
        paddingHorizontal: spacing.lg,
        paddingVertical: spacing.md,
        minHeight: 44,
      },
      lg: {
        paddingHorizontal: spacing.xl,
        paddingVertical: spacing.lg,
        minHeight: 52,
      },
    }

    // Variant styles - minimal/white aesthetic
    const variantStyles: Record<string, ViewStyle> = {
      primary: {
        backgroundColor: colors.text,
        borderWidth: 1,
        borderColor: colors.text,
      },
      secondary: {
        backgroundColor: colors.surface,
        borderWidth: 1,
        borderColor: colors.border,
      },
      outline: {
        backgroundColor: "transparent",
        borderWidth: 1,
        borderColor: colors.border,
      },
      ghost: { backgroundColor: "transparent" },
    }

    return {
      ...baseStyle,
      ...sizeStyles[size],
      ...variantStyles[variant],
      opacity: disabled || loading ? 0.6 : 1,
    }
  }

  const getTextStyles = (): TextStyle => {
    const textColors: Record<string, string> = {
      primary: colors.background,
      secondary: colors.text,
      outline: colors.text,
      ghost: colors.textMuted,
    }

    const sizeStyles: Record<string, TextStyle> = {
      sm: { fontSize: 14 },
      md: { fontSize: 16 },
      lg: { fontSize: 18 },
    }

    return {
      ...typography.label,
      ...sizeStyles[size],
      color: textColors[variant],
    }
  }

  return (
    <TouchableOpacity
      style={[getButtonStyles(), style]}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.7}
    >
      {loading ? (
        <ActivityIndicator
          color={variant === "primary" ? colors.background : colors.text}
          size="small"
        />
      ) : (
        <>
          {icon}
          <Text style={getTextStyles()}>{title}</Text>
        </>
      )}
    </TouchableOpacity>
  )
}
