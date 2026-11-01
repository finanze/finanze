import { forwardRef } from "react"
import { AnimatePresence, motion, useReducedMotion } from "framer-motion"
import type { HTMLMotionProps } from "framer-motion"
import { cn } from "@/lib/utils"

type AnimatedPopupProps = Omit<
  HTMLMotionProps<"div">,
  "animate" | "exit" | "initial" | "transition" | "ref"
> & {
  open: boolean
}

const popupEase = [0.16, 1, 0.3, 1] as const
const popupExitEase = [0.42, 0, 0.58, 1] as const

export const AnimatedPopup = forwardRef<HTMLDivElement, AnimatedPopupProps>(
  ({ open, className, children, ...props }, ref) => {
    const reducedMotion = useReducedMotion()
    const distance = reducedMotion ? 0 : 8
    const scale = reducedMotion ? 1 : 0.98
    const enterDuration = reducedMotion ? 0 : 0.2
    const exitDuration = reducedMotion ? 0 : 0.2

    return (
      <AnimatePresence>
        {open && (
          <motion.div
            ref={ref}
            key="popup"
            initial={{ opacity: 0, y: -distance, scale }}
            animate={{
              opacity: 1,
              y: 0,
              scale: 1,
              transition: { duration: enterDuration, ease: popupEase },
            }}
            exit={{
              opacity: 0,
              y: -distance,
              scale,
              transition: { duration: exitDuration, ease: popupExitEase },
            }}
            className={cn("origin-top", className)}
            {...props}
          >
            {children}
          </motion.div>
        )}
      </AnimatePresence>
    )
  },
)

AnimatedPopup.displayName = "AnimatedPopup"
