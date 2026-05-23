import { useLayoutScroll } from "@/context/LayoutScrollContext"
import { useTheme } from "@/context/ThemeContext"
import { isNativeMobile, isPWAStandalone } from "@/lib/platform"
import { StatusBar, Style } from "@capacitor/status-bar"
import { motion } from "framer-motion"
import { useEffect } from "react"

const BLUR_LAYERS = [
  {
    blur: 2.5,
    mask: "linear-gradient(rgba(0,0,0,1), rgba(0,0,0,1) 30%, rgba(0,0,0,0) 50%)",
  },
  {
    blur: 2,
    mask: "linear-gradient(rgba(0,0,0,0) 15%, rgba(0,0,0,1) 30%, rgba(0,0,0,1) 50%, rgba(0,0,0,0) 65%)",
  },
  {
    blur: 1.5,
    mask: "linear-gradient(rgba(0,0,0,0) 35%, rgba(0,0,0,1) 45%, rgba(0,0,0,1) 65%, rgba(0,0,0,0) 80%)",
  },
  {
    blur: 0.5,
    mask: "linear-gradient(rgba(0,0,0,0) 50%, rgba(0,0,0,1) 60%, rgba(0,0,0,1) 80%, rgba(0,0,0,0) 95%)",
  },
]

export function StatusBarBlur() {
  const { atTop } = useLayoutScroll()
  const { resolvedTheme } = useTheme()
  const isMobile = isNativeMobile()
  const isPWA = isPWAStandalone()

  useEffect(() => {
    if (!isMobile) return
    const style = !atTop
      ? Style.Dark
      : resolvedTheme === "dark"
        ? Style.Dark
        : Style.Light
    StatusBar.setStyle({ style })
  }, [atTop, resolvedTheme, isMobile])

  const isDark = resolvedTheme === "dark"

  if (!isMobile && !isPWA) return null

  const darkGradient = isDark
    ? "linear-gradient(to bottom, rgba(0,0,0,1) 0%, rgba(0,0,0,0.98) 5%, rgba(0,0,0,0.96) 10%, rgba(0,0,0,0.94) 15%, rgba(0,0,0,0.90) 20%, rgba(0,0,0,0.84) 25%, rgba(0,0,0,0.76) 30%, rgba(0,0,0,0.67) 35%, rgba(0,0,0,0.56) 40%, rgba(0,0,0,0.45) 45%, rgba(0,0,0,0.35) 50%, rgba(0,0,0,0.26) 55%, rgba(0,0,0,0.18) 60%, rgba(0,0,0,0.12) 65%, rgba(0,0,0,0.07) 70%, rgba(0,0,0,0.04) 75%, rgba(0,0,0,0.01) 80%, rgba(0,0,0,0.005) 85%, transparent 90%)"
    : "linear-gradient(to bottom, rgba(0,0,0,0.55) 0%, rgba(0,0,0,0.54) 5%, rgba(0,0,0,0.52) 10%, rgba(0,0,0,0.49) 15%, rgba(0,0,0,0.45) 20%, rgba(0,0,0,0.40) 25%, rgba(0,0,0,0.34) 30%, rgba(0,0,0,0.28) 35%, rgba(0,0,0,0.22) 40%, rgba(0,0,0,0.17) 45%, rgba(0,0,0,0.12) 50%, rgba(0,0,0,0.08) 55%, rgba(0,0,0,0.05) 60%, rgba(0,0,0,0.03) 65%, rgba(0,0,0,0.01) 70%, rgba(0,0,0,0.005) 75%, transparent 80%)"

  return (
    <motion.div
      className="fixed top-0 left-0 right-0 z-50 pointer-events-none"
      initial={{ y: "-100%" }}
      animate={{ y: atTop ? "-100%" : "0%" }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      style={{
        height: "calc(var(--safe-area-inset-top, 0px) + 52px)",
      }}
    >
      {BLUR_LAYERS.map((layer, i) => (
        <div
          key={i}
          style={{
            position: "absolute",
            inset: 0,
            backdropFilter: `blur(${layer.blur}px)`,
            WebkitBackdropFilter: `blur(${layer.blur}px)`,
            mask: layer.mask,
            WebkitMask: layer.mask,
          }}
        />
      ))}
      <div
        style={{
          position: "absolute",
          inset: 0,
          background: darkGradient,
        }}
      />
    </motion.div>
  )
}
