import {
  createContext,
  useContext,
  useState,
  useCallback,
  type ReactNode,
} from "react"
import { BackupMode, SyncStatus } from "@/types"

export type BackupAlertColor = "red" | "dark-red" | "orange" | null

interface BackupAlertContextType {
  alertColor: BackupAlertColor
  updateAlertStatus: (
    overallStatus: SyncStatus | null,
    backupMode: BackupMode,
    hasCredentialsMismatch?: boolean,
  ) => void
}

const BackupAlertContext = createContext<BackupAlertContextType | undefined>(
  undefined,
)

function computeAlertColor(
  overallStatus: SyncStatus | null,
  backupMode: BackupMode,
  hasCredentialsMismatch: boolean,
): BackupAlertColor {
  if (hasCredentialsMismatch) {
    return "dark-red"
  }

  if (overallStatus === SyncStatus.CONFLICT) {
    return "red"
  }

  if (
    backupMode === BackupMode.MANUAL &&
    overallStatus === SyncStatus.OUTDATED
  ) {
    return "orange"
  }

  return null
}

export function BackupAlertProvider({ children }: { children: ReactNode }) {
  const [alertColor, setAlertColor] = useState<BackupAlertColor>(null)

  const updateAlertStatus = useCallback(
    (
      overallStatus: SyncStatus | null,
      backupMode: BackupMode,
      hasCredentialsMismatch = false,
    ) => {
      const color = computeAlertColor(
        overallStatus,
        backupMode,
        hasCredentialsMismatch,
      )
      setAlertColor(prev => (prev === color ? prev : color))
    },
    [],
  )

  return (
    <BackupAlertContext.Provider value={{ alertColor, updateAlertStatus }}>
      {children}
    </BackupAlertContext.Provider>
  )
}

export function useBackupAlert(): Pick<BackupAlertContextType, "alertColor"> {
  const context = useContext(BackupAlertContext)
  if (!context) {
    return { alertColor: null }
  }
  return { alertColor: context.alertColor }
}

export function useBackupAlertUpdater(): Pick<
  BackupAlertContextType,
  "updateAlertStatus"
> {
  const context = useContext(BackupAlertContext)
  if (!context) {
    return { updateAlertStatus: () => {} }
  }
  return { updateAlertStatus: context.updateAlertStatus }
}
