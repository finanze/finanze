import { motion } from "framer-motion"
import { useI18n } from "@/i18n"
import { SavingsCalculator } from "@/components/calculations/SavingsCalculator"
import { useSkipMountAnimation } from "@/lib/animations"

export default function CalculationsPage() {
  const { t } = useI18n()
  const skipAnimations = useSkipMountAnimation(true)

  return (
    <motion.div
      className="space-y-6"
      initial={skipAnimations ? false : { opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.3 }}
    >
      <div className="flex items-center justify-between gap-2">
        <h1 className="text-3xl font-bold text-gray-900 dark:text-gray-100 shrink-0">
          {t.calculations.title}
        </h1>
      </div>

      <SavingsCalculator />
    </motion.div>
  )
}
