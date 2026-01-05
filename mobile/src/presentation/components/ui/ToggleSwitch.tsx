import React from "react"
import { Animated, Pressable, StyleProp, ViewStyle } from "react-native"
import { useTheme } from "@/presentation/context"
import { getThemeColors } from "@/presentation/theme"

type ToggleSwitchProps = {
  value: boolean
  onValueChange: (value: boolean) => void
  disabled?: boolean
  style?: StyleProp<ViewStyle>
  accessibilityLabel?: string
}

export function ToggleSwitch({
  value,
  onValueChange,
  disabled = false,
  style,
  accessibilityLabel,
}: ToggleSwitchProps) {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)

  const translateX = React.useRef(new Animated.Value(value ? 18 : 0)).current

  React.useEffect(() => {
    Animated.timing(translateX, {
      toValue: value ? 18 : 0,
      duration: 140,
      useNativeDriver: true,
    }).start()
  }, [translateX, value])

  // Minimal/luxury: neutral, high-contrast, no accent color.
  // ON: inverted (track uses text color, thumb uses elevated surface)
  // OFF: subtle (track uses surface + border)
  const trackColor = value ? colors.text : colors.surface
  const borderColor = value ? colors.text : colors.textMuted
  const thumbColor = colors.surfaceElevated
  const thumbBorderColor = value ? colors.text : colors.textMuted

  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityState={{ checked: value, disabled }}
      accessibilityLabel={accessibilityLabel}
      disabled={disabled}
      onPress={() => onValueChange(!value)}
      style={[
        {
          width: 44,
          height: 26,
          borderRadius: 26,
          padding: 3,
          backgroundColor: trackColor,
          borderWidth: 1,
          borderColor,
          opacity: disabled ? 0.55 : 1,
          justifyContent: "center",
        },
        style,
      ]}
    >
      <Animated.View
        style={{
          width: 20,
          height: 20,
          borderRadius: 20,
          backgroundColor: thumbColor,
          borderWidth: 1,
          borderColor: thumbBorderColor,
          transform: [{ translateX }],
        }}
      />
    </Pressable>
  )
}
