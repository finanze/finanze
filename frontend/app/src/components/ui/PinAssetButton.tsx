import React from "react"
import { Button } from "./Button"
import { usePinnedAssets, AssetId } from "@/context/PinnedAssetsContext"
import { Pin, PinOff } from "lucide-react"
import { useI18n } from "@/i18n"

interface Props {
  assetId: AssetId
  className?: string
  size?: "sm" | "default" | "icon"
}

export const PinAssetButton: React.FC<Props> = ({
  assetId,
  className,
  size,
}) => {
  const { isPinned, togglePin } = usePinnedAssets()
  const { t } = useI18n()
  const pinned = isPinned(assetId)
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
      {pinned ? (
        <PinOff size={16} className="mr-1" />
      ) : (
        <Pin size={16} className="mr-1" />
      )}
      <span className="hidden md:inline">
        {pinned ? t.common.unpin : t.common.pin}
      </span>
    </Button>
  )
}
