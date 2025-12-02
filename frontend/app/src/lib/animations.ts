import { useRef, useState, useLayoutEffect } from "react"
import type { Variants } from "framer-motion"

export const fadeListContainer: Variants = {
  hidden: { opacity: 0 },
  show: {
    opacity: 1,
    transition: { staggerChildren: 0.08 },
  },
}

export const fadeListItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  show: { opacity: 1, y: 0 },
}

export function useSkipMountAnimation(isReady: boolean = true): boolean {
  const hasBeenReady = useRef(false)
  const [shouldSkip, setShouldSkip] = useState(false)

  useLayoutEffect(() => {
    if (isReady && !hasBeenReady.current) {
      hasBeenReady.current = true
      setShouldSkip(true)
    }
  }, [isReady])

  if (!isReady) return true

  return shouldSkip
}

export const cardEntranceVariants: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0 },
}

export function getInitialAnimationState(
  skipAnimations: boolean,
  variant: "hidden" | { opacity: number; y: number } = "hidden",
): false | "hidden" | { opacity: number; y: number } {
  return skipAnimations ? false : variant
}
