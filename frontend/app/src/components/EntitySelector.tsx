import { useState, useEffect, useMemo, type ReactNode } from "react"
import { Check, Landmark, Wallet, ArrowLeftRight, Package } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { useI18n } from "@/i18n"
import { getImageUrl } from "@/services/api"
import { EntityOrigin, EntityType, type Entity } from "@/types"
import { cn } from "@/lib/utils"

const ENTITY_TYPE_ICONS: Record<string, typeof Landmark> = {
  [EntityType.FINANCIAL_INSTITUTION]: Landmark,
  [EntityType.CRYPTO_WALLET]: Wallet,
  [EntityType.CRYPTO_EXCHANGE]: ArrowLeftRight,
  [EntityType.COMMODITY]: Package,
}

interface EntitySelectorProps {
  entities: Entity[]
  selectedEntityIds: string[]
  onSelectionChange: (entityIds: string[]) => void
  singleSelect?: boolean
  disabled?: boolean
  placeholder?: string
  description?: string
  warningBanner?: ReactNode
  entityWarning?: (entity: Entity) => boolean
  emptyMessage?: string
  emptySelectionBadge?: string
  className?: string
  entityImageOverride?: (entity: Entity) => string | null | undefined
}

function EntityIcon({
  entity,
  src,
  className,
}: {
  entity: Entity
  src: string | undefined
  className?: string
}) {
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    setFailed(false)
  }, [src])

  if (!src || failed) {
    const Icon = ENTITY_TYPE_ICONS[entity.type] ?? Package
    return (
      <div
        className={cn(
          "flex items-center justify-center bg-muted rounded-md",
          className,
        )}
      >
        <Icon className="h-1/2 w-1/2 text-muted-foreground" />
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={entity.name}
      draggable={false}
      className={cn("object-contain select-none", className)}
      onError={() => setFailed(true)}
    />
  )
}

export function EntitySelector({
  entities: displayEntities,
  selectedEntityIds,
  onSelectionChange,
  singleSelect = false,
  disabled = false,
  placeholder,
  description,
  warningBanner,
  entityWarning,
  emptyMessage,
  emptySelectionBadge,
  className,
  entityImageOverride,
}: EntitySelectorProps) {
  const { t } = useI18n()
  const [open, setOpen] = useState(false)
  const [entityImages, setEntityImages] = useState<Record<string, string>>({})

  const defaultPlaceholder = placeholder || t.transactions.selectEntities

  useEffect(() => {
    const loadImages = async () => {
      const images: Record<string, string> = {}
      for (const entity of displayEntities) {
        const override = entityImageOverride?.(entity)
        if (override) {
          images[entity.id] = override
          continue
        }
        try {
          if (entity.icon_url) {
            images[entity.id] = entity.icon_url
          } else if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
            images[entity.id] = await getImageUrl(
              `/static/entities/logos/${entity.id}.png`,
            )
          } else if (entity.origin === EntityOrigin.NATIVE) {
            images[entity.id] = `entities/${entity.id}.png`
          } else {
            images[entity.id] = ""
          }
        } catch {
          images[entity.id] = ""
        }
      }
      setEntityImages(images)
    }
    loadImages()
  }, [displayEntities, entityImageOverride])

  const toggleEntity = (entityId: string) => {
    if (singleSelect) {
      if (selectedEntityIds.includes(entityId)) {
        onSelectionChange([])
      } else {
        onSelectionChange([entityId])
      }
      setOpen(false)
      return
    }
    if (selectedEntityIds.includes(entityId)) {
      onSelectionChange(selectedEntityIds.filter(id => id !== entityId))
    } else {
      onSelectionChange([...selectedEntityIds, entityId])
    }
  }

  const selectedEntities = useMemo(
    () =>
      displayEntities.filter(entity => selectedEntityIds.includes(entity.id)),
    [displayEntities, selectedEntityIds],
  )

  if (displayEntities.length === 0 && emptyMessage) {
    return (
      <div className="text-sm text-muted-foreground italic">{emptyMessage}</div>
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className={cn("w-full max-w-sm justify-between", className)}
          disabled={disabled || displayEntities.length === 0}
        >
          <div className="flex items-center gap-2 overflow-hidden">
            {selectedEntities.length > 0 ? (
              singleSelect ? (
                <div className="flex items-center gap-1.5 overflow-hidden select-none">
                  <div className="h-5 w-5 flex-shrink-0 overflow-hidden rounded">
                    <EntityIcon
                      entity={selectedEntities[0]}
                      src={entityImages[selectedEntities[0].id]}
                      className="h-full w-full"
                    />
                  </div>
                  <span className="truncate text-sm">
                    {selectedEntities[0].name}
                  </span>
                </div>
              ) : (
                <div className="flex items-center gap-1.5 overflow-hidden select-none">
                  {selectedEntities.slice(0, 5).map(entity => (
                    <div
                      key={entity.id}
                      className="h-5 w-5 flex-shrink-0 overflow-hidden rounded"
                    >
                      <EntityIcon
                        entity={entity}
                        src={entityImages[entity.id]}
                        className="h-full w-full"
                      />
                    </div>
                  ))}
                  {selectedEntities.length > 5 && (
                    <span className="text-xs text-muted-foreground">
                      +{selectedEntities.length - 5}
                    </span>
                  )}
                </div>
              )
            ) : (
              <span className="text-muted-foreground">
                {defaultPlaceholder}
              </span>
            )}
          </div>
          {!singleSelect &&
            (selectedEntities.length > 0 || emptySelectionBadge) && (
              <Badge variant="secondary" className="ml-2 flex-shrink-0">
                {selectedEntities.length > 0
                  ? selectedEntities.length
                  : emptySelectionBadge}
              </Badge>
            )}
        </Button>
      </PopoverTrigger>
      <PopoverContent
        className="w-80 max-w-[calc(100vw-2rem)] p-0"
        align="start"
      >
        <div>
          {description && (
            <p className="text-xs text-muted-foreground px-0.5 m-1.5">
              {description}
            </p>
          )}
          <div className="grid grid-cols-3 p-1 max-h-52 overflow-y-auto">
            {displayEntities.map(entity => {
              const isSelected = selectedEntityIds.includes(entity.id)
              const hasWarning = entityWarning?.(entity) ?? false

              return (
                <button
                  key={entity.id}
                  type="button"
                  onClick={() => toggleEntity(entity.id)}
                  className={cn(
                    "relative flex flex-col items-center gap-1 rounded-lg border p-1.5 m-1 transition-all hover:bg-accent select-none min-w-0",
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-border/50 bg-background/50",
                  )}
                >
                  <div className="relative flex-shrink-0">
                    <div className="h-7 w-7 overflow-hidden rounded-md">
                      <EntityIcon
                        entity={entity}
                        src={entityImages[entity.id]}
                        className="h-full w-full"
                      />
                    </div>
                    {isSelected && (
                      <div className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary">
                        <Check className="h-2.5 w-2.5 text-primary-foreground" />
                      </div>
                    )}
                    {hasWarning && (
                      <div className="absolute -top-1 -right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500">
                        <span className="text-[8px] font-bold text-white">
                          !
                        </span>
                      </div>
                    )}
                  </div>
                  <span className="max-w-full truncate text-[10px] leading-tight text-center select-none">
                    {entity.name}
                  </span>
                </button>
              )
            })}
          </div>
          {warningBanner}
        </div>
      </PopoverContent>
    </Popover>
  )
}
