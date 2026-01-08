import React, { useEffect } from "react"
import { router } from "expo-router"
import { Tabs } from "expo-router"
import { useTheme } from "@/presentation/context"
import { useAuth } from "@/presentation/context"
import { LayoutMenuScrollProvider } from "@/presentation/context"
import { getThemeColors } from "@/presentation/theme"
import { StyleSheet, View } from "react-native"
import { ArrowLeftRight, LayoutDashboard, Settings } from "lucide-react-native"
import { FloatingTabBar } from "@/presentation/components/navigation/FloatingTabBar"

export default function TabsLayout() {
  const { resolvedTheme } = useTheme()
  const colors = getThemeColors(resolvedTheme)
  const { session, isInitialized } = useAuth()

  useEffect(() => {
    if (!isInitialized) return
    if (!session) {
      router.replace("/(auth)/login")
    }
  }, [isInitialized, session])

  return (
    <LayoutMenuScrollProvider>
      <View style={[styles.root, { backgroundColor: colors.background }]}>
        <Tabs
          screenOptions={{
            headerShown: false,
          }}
          tabBar={props => <FloatingTabBar {...props} />}
        >
          <Tabs.Screen
            name="dashboard"
            options={{
              title: "Dashboard",
              tabBarIcon: ({ color, size }) => (
                <LayoutDashboard size={size} color={color} />
              ),
            }}
          />
          <Tabs.Screen
            name="transactions"
            options={{
              title: "Transactions",
              tabBarIcon: ({ color, size }) => (
                <ArrowLeftRight size={size} color={color} />
              ),
            }}
          />

          <Tabs.Screen
            name="settings"
            options={{
              title: "Settings",
              tabBarIcon: ({ color, size }) => (
                <Settings size={size} color={color} />
              ),
            }}
          />
        </Tabs>
      </View>
    </LayoutMenuScrollProvider>
  )
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
  },
})
