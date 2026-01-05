import React, {
  createContext,
  useCallback,
  useContext,
  useMemo,
  useState,
  type ReactNode,
} from "react"

import type { ApplicationContainer } from "@/domain/applicationContainer"
import {
  getOrCreateApplicationContainer,
  resetApplicationContainer,
} from "@/di"

interface ApplicationContainerContextValue {
  container: ApplicationContainer
  reset: () => Promise<void>
}

const ApplicationContainerContext = createContext<
  ApplicationContainerContextValue | undefined
>(undefined)

export function ApplicationContainerProvider({
  children,
}: {
  children: ReactNode
}) {
  const [container, setContainer] = useState<ApplicationContainer>(() =>
    getOrCreateApplicationContainer(),
  )

  const reset = useCallback(async () => {
    await resetApplicationContainer()
    setContainer(getOrCreateApplicationContainer())
  }, [])

  const value = useMemo(
    () => ({
      container,
      reset,
    }),
    [container, reset],
  )

  return (
    <ApplicationContainerContext.Provider value={value}>
      {children}
    </ApplicationContainerContext.Provider>
  )
}

export function useApplicationContainer(): ApplicationContainer {
  const ctx = useContext(ApplicationContainerContext)
  if (!ctx) {
    throw new Error(
      "useApplicationContainer must be used within an ApplicationContainerProvider",
    )
  }
  return ctx.container
}

export function useResetApplicationContainer(): () => Promise<void> {
  const ctx = useContext(ApplicationContainerContext)
  if (!ctx) {
    throw new Error(
      "useResetApplicationContainer must be used within an ApplicationContainerProvider",
    )
  }
  return ctx.reset
}
