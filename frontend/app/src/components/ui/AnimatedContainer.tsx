import { memo, type ReactNode } from "react"
import { motion } from "framer-motion"

interface AnimatedContainerProps {
  children: ReactNode
  className?: string
  skipAnimation: boolean
  delay?: number
}

export const AnimatedContainer = memo(function AnimatedContainer({
  children,
  className,
  skipAnimation,
  delay = 0,
}: AnimatedContainerProps) {
  return (
    <motion.div
      initial={skipAnimation ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={skipAnimation ? { duration: 0 } : { delay }}
      className={className}
    >
      {children}
    </motion.div>
  )
})
