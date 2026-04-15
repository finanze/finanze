import { useEffect, useId } from "react"
import { useModalRegistry } from "@/context/ModalRegistryContext"

export function useModalBackHandler(isOpen: boolean, onClose: () => void) {
  const { register } = useModalRegistry()
  const id = useId()

  useEffect(() => {
    if (!isOpen) return
    return register(id, onClose)
  }, [isOpen, onClose, register, id])
}
