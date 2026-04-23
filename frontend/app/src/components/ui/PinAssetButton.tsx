import React from "react"
import { Button } from "./Button"
import {
  usePinnedShortcuts,
  type PinnedShortcutId,
} from "@/context/PinnedShortcutsContext"
import { Pin } from "lucide-react"
import { useI18n } from "@/i18n"

type Breakpoint = "sm" | "md" | "lg" | "xl"

interface Props {
  assetId: PinnedShortcutId
  className?: string
  size?: "sm" | "default" | "icon"
  showLabelFrom?: Breakpoint
}

export const PinAssetButton: React.FC<Props> = ({
  assetId,
  className,
  size,
  showLabelFrom = "md",
}) => {
  const { isPinned, togglePin } = usePinnedShortcuts()
  const { t } = useI18n()
  const pinned = isPinned(assetId)
  const labelClassName =
    size === "icon"
      ? "hidden"
      : showLabelFrom
        ? `hidden ${showLabelFrom}:inline`
        : ""
  return (
    <Button
      variant="ghost"
      size={size || "sm"}
      className={className}
      onClick={e => {
        e.stopPropagation()
        togglePin(assetId)
      }}
      title={pinned ? t.common.unpinAsset : t.common.pinAsset}
    >
      <Pin
        size={16}
        className={
          size === "icon"
            ? pinned
              ? "fill-current"
              : ""
            : pinned
              ? "mr-1 fill-current"
              : "mr-1"
        }
      />
      <span className={labelClassName}>
        {pinned ? t.common.unpin : t.common.pin}
      </span>
    </Button>
  )
}
