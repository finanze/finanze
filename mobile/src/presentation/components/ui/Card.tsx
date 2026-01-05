import React from "react"
import { View, StyleSheet, ViewStyle, StyleProp } from "react-native"
import { useTheme } from "../../context/ThemeContext"
import { getThemeColors, borderRadius, spacing } from "../../theme"

interface CardProps {
  children: React.ReactNode
  style?: StyleProp<ViewStyle>
  elevated?: boolean
}

export function Card({ children, style, elevated = false }: CardProps) {
  const { resolvedTheme: colorScheme } = useTheme()
  const colors = getThemeColors(colorScheme)

  return (
    <View
      style={[
        styles.card,
        {
          backgroundColor: elevated ? colors.surfaceElevated : colors.surface,
          borderColor: colors.border,
        },
        elevated && styles.elevated,
        style,
      ]}
    >
      {children}
    </View>
  )
}

const styles = StyleSheet.create({
  card: {
    borderRadius: borderRadius.xl,
    padding: spacing.lg,
    borderWidth: 1,
  },
  elevated: {
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.1,
    shadowRadius: 4,
    elevation: 3,
  },
})
