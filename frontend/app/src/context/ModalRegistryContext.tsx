import React, { createContext, useCallback, useContext, useRef } from "react"

interface ModalEntry {
  id: string
  onDismiss: () => void
}

interface ModalRegistryContextValue {
  register: (id: string, onDismiss: () => void) => () => void
  dismissTop: () => boolean
  hasOpen: () => boolean
}

const ModalRegistryContext = createContext<ModalRegistryContextValue | null>(
  null,
)

export function ModalRegistryProvider({
  children,
}: {
  children: React.ReactNode
}) {
  const stackRef = useRef<ModalEntry[]>([])

  const register = useCallback((id: string, onDismiss: () => void) => {
    stackRef.current = [
      ...stackRef.current.filter(e => e.id !== id),
      { id, onDismiss },
    ]
    return () => {
      stackRef.current = stackRef.current.filter(e => e.id !== id)
    }
  }, [])

  const dismissTop = useCallback(() => {
    const stack = stackRef.current
    if (stack.length === 0) return false
    const top = stack[stack.length - 1]
    top.onDismiss()
    return true
  }, [])

  const hasOpen = useCallback(() => stackRef.current.length > 0, [])

  return (
    <ModalRegistryContext.Provider value={{ register, dismissTop, hasOpen }}>
      {children}
    </ModalRegistryContext.Provider>
  )
}

export function useModalRegistry() {
  const ctx = useContext(ModalRegistryContext)
  if (!ctx)
    throw new Error(
      "useModalRegistry must be used within ModalRegistryProvider",
    )
  return ctx
}
