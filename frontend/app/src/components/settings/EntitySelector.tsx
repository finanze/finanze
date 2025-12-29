import { useState, useEffect, useMemo } from "react"
import { Check, AlertTriangle } from "lucide-react"
import { Button } from "@/components/ui/Button"
import { Badge } from "@/components/ui/Badge"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import { useAppContext } from "@/context/AppContext"
import { useI18n } from "@/i18n"
import { getImageUrl } from "@/services/api"
import { EntityOrigin } from "@/types"
import { cn } from "@/lib/utils"
import {
  getAutoRefreshCompatibleEntities,
  entityHasPin,
} from "@/utils/autoRefreshUtils"

interface EntitySelectorProps {
  selectedEntityIds: string[]
  onSelectionChange: (entityIds: string[]) => void
  disabled?: boolean
}

export function EntitySelector({
  selectedEntityIds,
  onSelectionChange,
  disabled = false,
}: EntitySelectorProps) {
  const { t } = useI18n()
  const { entities } = useAppContext()
  const [open, setOpen] = useState(false)
  const [entityImages, setEntityImages] = useState<Record<string, string>>({})

  const compatibleEntities = useMemo(
    () => getAutoRefreshCompatibleEntities(entities),
    [entities],
  )

  const entitiesWithPin = useMemo(
    () => compatibleEntities.filter(entityHasPin),
    [compatibleEntities],
  )

  useEffect(() => {
    const loadImages = async () => {
      const images: Record<string, string> = {}
      for (const entity of compatibleEntities) {
        try {
          if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
            if (entity.icon_url) {
              images[entity.id] = entity.icon_url
            } else {
              images[entity.id] = await getImageUrl(
                `/static/entities/logos/${entity.id}.png`,
              )
            }
          } else {
            images[entity.id] = `entities/${entity.id}.png`
          }
        } catch {
          images[entity.id] = `entities/${entity.id}.png`
        }
      }
      setEntityImages(images)
    }
    loadImages()
  }, [compatibleEntities])

  const toggleEntity = (entityId: string) => {
    if (selectedEntityIds.includes(entityId)) {
      onSelectionChange(selectedEntityIds.filter(id => id !== entityId))
    } else {
      onSelectionChange([...selectedEntityIds, entityId])
    }
  }

  const selectedEntities = compatibleEntities.filter(entity =>
    selectedEntityIds.includes(entity.id),
  )

  const getDisplayText = () => {
    if (selectedEntityIds.length === 0) {
      return t.settings.dataSettings.autoRefresh.allEntities
    }
    return t.settings.dataSettings.autoRefresh.selectedCount.replace(
      "{count}",
      selectedEntityIds.length.toString(),
    )
  }

  if (compatibleEntities.length === 0) {
    return (
      <div className="text-sm text-muted-foreground italic">
        {t.settings.dataSettings.autoRefresh.noEntitiesAvailable}
      </div>
    )
  }

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <Button
          variant="outline"
          role="combobox"
          aria-expanded={open}
          className="w-full max-w-sm justify-between"
          disabled={disabled}
        >
          <div className="flex items-center gap-2 overflow-hidden">
            {selectedEntities.length > 0 ? (
              <div className="flex items-center gap-1.5 overflow-hidden">
                {selectedEntities.slice(0, 3).map(entity => (
                  <div
                    key={entity.id}
                    className="h-5 w-5 flex-shrink-0 overflow-hidden rounded"
                  >
                    <img
                      src={entityImages[entity.id]}
                      alt={entity.name}
                      className="h-full w-full object-contain"
                      onError={e =>
                        (e.currentTarget.src =
                          "entities/entity_placeholder.png")
                      }
                    />
                  </div>
                ))}
                {selectedEntities.length > 3 && (
                  <span className="text-xs text-muted-foreground">
                    +{selectedEntities.length - 3}
                  </span>
                )}
              </div>
            ) : (
              <span className="text-muted-foreground">
                {t.settings.dataSettings.autoRefresh.entitiesPlaceholder}
              </span>
            )}
          </div>
          <Badge variant="secondary" className="ml-2 flex-shrink-0">
            {getDisplayText()}
          </Badge>
        </Button>
      </PopoverTrigger>
      <PopoverContent className="w-80 p-3" align="start">
        <div className="space-y-3">
          <p className="text-xs text-muted-foreground">
            {t.settings.dataSettings.autoRefresh.entitiesDescription}
          </p>
          <div className="grid grid-cols-3 gap-2 max-h-48 overflow-y-auto">
            {compatibleEntities.map(entity => {
              const isSelected = selectedEntityIds.includes(entity.id)
              const hasPin = entityHasPin(entity)

              return (
                <button
                  key={entity.id}
                  type="button"
                  onClick={() => toggleEntity(entity.id)}
                  className={cn(
                    "relative flex flex-col items-center gap-1.5 rounded-lg border p-2 transition-all hover:bg-accent",
                    isSelected
                      ? "border-primary bg-primary/5"
                      : "border-border/50 bg-background/50",
                  )}
                >
                  <div className="relative">
                    <div className="h-8 w-8 overflow-hidden rounded-md">
                      <img
                        src={entityImages[entity.id]}
                        alt={entity.name}
                        className="h-full w-full object-contain"
                        onError={e =>
                          (e.currentTarget.src =
                            "entities/entity_placeholder.png")
                        }
                      />
                    </div>
                    {isSelected && (
                      <div className="absolute -bottom-1 -right-1 flex h-4 w-4 items-center justify-center rounded-full bg-primary">
                        <Check className="h-2.5 w-2.5 text-primary-foreground" />
                      </div>
                    )}
                    {hasPin && (
                      <div className="absolute -top-1 -right-1 flex h-3.5 w-3.5 items-center justify-center rounded-full bg-amber-500">
                        <AlertTriangle className="h-2 w-2 text-white" />
                      </div>
                    )}
                  </div>
                  <span className="max-w-full truncate text-[10px] leading-tight text-center">
                    {entity.name}
                  </span>
                </button>
              )
            })}
          </div>
          {entitiesWithPin.length > 0 && (
            <div className="flex items-start gap-2 rounded-md bg-amber-500/10 p-2 text-xs">
              <AlertTriangle className="mt-0.5 h-3 w-3 flex-shrink-0 text-amber-500" />
              <p className="text-muted-foreground">
                {t.settings.dataSettings.autoRefresh.pinWarningTooltip}
              </p>
            </div>
          )}
        </div>
      </PopoverContent>
    </Popover>
  )
}
