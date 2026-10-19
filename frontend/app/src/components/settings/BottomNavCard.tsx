import { useEffect, useState } from "react"
import { Reorder, useDragControls } from "framer-motion"
import {
  ArrowDownToLine,
  ArrowUpToLine,
  GripVertical,
  LockKeyhole,
  MoreVertical,
  PanelBottom,
  Plus,
  RotateCcw,
  X,
} from "lucide-react"
import { useI18n } from "@/i18n"
import {
  BOTTOM_NAV_SHORTCUTS,
  MAX_BAR_ITEMS,
  MIN_BAR_ITEMS,
  useBottomNav,
  type BottomNavItemId,
} from "@/context/BottomNavContext"
import {
  useBottomNavCatalog,
  type BottomNavEntry,
} from "@/components/layout/bottomNavItems"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/Card"
import { Button } from "@/components/ui/Button"
import { cn } from "@/lib/utils"

interface NavRowProps {
  id: BottomNavItemId
  entry: BottomNavEntry
  inBar: boolean
  atLimit: boolean
  move: () => void
  remove?: () => void
  reorder: (direction: number) => void
}

function NavRow({
  id,
  entry,
  inBar,
  atLimit,
  move,
  remove,
  reorder,
}: NavRowProps) {
  const controls = useDragControls()
  const { t } = useI18n()
  const copy = t.settings.bottomNav
  const moveLabel = (inBar ? copy.moveToMenu : copy.moveToBar).replace(
    "{page}",
    entry.label,
  )
  const limitLabel = inBar ? copy.minimum : copy.maximum
  return (
    <Reorder.Item
      value={id}
      dragListener={false}
      dragControls={controls}
      className="relative flex min-h-14 items-center gap-2 rounded-md bg-background py-1 pr-1"
      whileDrag={{ zIndex: 10, boxShadow: "0 4px 16px #00000020" }}
      data-testid={`bottom-nav-row-${id}`}
    >
      <Button
        variant="ghost"
        size="icon"
        className="h-11 w-9 shrink-0 touch-none cursor-grab active:cursor-grabbing text-muted-foreground"
        aria-label={copy.reorder.replace("{page}", entry.label)}
        title={copy.reorder.replace("{page}", entry.label)}
        aria-keyshortcuts="ArrowUp ArrowDown"
        onTouchStartCapture={event => event.stopPropagation()}
        onPointerDown={event => controls.start(event)}
        onKeyDown={event => {
          if (event.key !== "ArrowUp" && event.key !== "ArrowDown") return
          event.preventDefault()
          reorder(event.key === "ArrowUp" ? -1 : 1)
        }}
      >
        <GripVertical className="h-4 w-4" />
      </Button>
      {entry.renderIcon("h-4 w-4 shrink-0 text-muted-foreground")}
      <span className="min-w-0 flex-1 break-words text-sm leading-snug">
        {entry.label}
      </span>
      <span title={atLimit ? limitLabel : moveLabel}>
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-9 shrink-0"
          disabled={atLimit}
          aria-label={moveLabel}
          onClick={move}
        >
          {inBar ? (
            <ArrowDownToLine className="h-4 w-4" />
          ) : (
            <ArrowUpToLine className="h-4 w-4" />
          )}
        </Button>
      </span>
      {remove && (
        <Button
          variant="ghost"
          size="icon"
          className="h-11 w-9 shrink-0 text-muted-foreground"
          aria-label={copy.remove.replace("{page}", entry.label)}
          title={copy.remove.replace("{page}", entry.label)}
          onClick={remove}
        >
          <X className="h-4 w-4" />
        </Button>
      )}
    </Reorder.Item>
  )
}

export function BottomNavCard() {
  const { t } = useI18n()
  const copy = t.settings.bottomNav
  const catalog = useBottomNavCatalog()
  const nav = useBottomNav()
  const [narrow, setNarrow] = useState(
    () => typeof window !== "undefined" && window.innerWidth < 768,
  )
  const [pickerOpen, setPickerOpen] = useState(false)
  const { setIsCustomizing } = nav

  useEffect(() => {
    if (!narrow) return
    setIsCustomizing(true)
    return () => setIsCustomizing(false)
  }, [narrow, setIsCustomizing])

  useEffect(() => {
    const resize = () => setNarrow(window.innerWidth < 768)
    window.addEventListener("resize", resize)
    return () => window.removeEventListener("resize", resize)
  }, [])

  if (!narrow) return null

  const available = BOTTOM_NAV_SHORTCUTS.filter(
    id => !nav.bar.includes(id) && !nav.menu.includes(id),
  )
  const reorderByKey = (
    list: "bar" | "menu",
    id: BottomNavItemId,
    direction: number,
  ) => {
    const ids = [...nav[list]]
    const index = ids.indexOf(id)
    const next = index + direction
    if (index < 0 || next < 0 || next >= ids.length) return
    ;[ids[index], ids[next]] = [ids[next], ids[index]]
    if (list === "bar") nav.reorderBar(ids)
    else nav.reorderMenu(ids)
  }

  return (
    <Card
      className="-mx-6 md:mx-0 rounded-none md:rounded-lg border-x-0 md:border-x"
      data-testid="bottom-nav-settings"
    >
      <CardHeader>
        <div className="flex items-center gap-2">
          <PanelBottom className="h-5 w-5 text-primary" />
          <CardTitle className="text-lg tracking-normal">
            {copy.title}
          </CardTitle>
        </div>
      </CardHeader>
      <CardContent className="space-y-5">
        <section aria-label={copy.inBar}>
          <div className="flex flex-wrap items-center justify-between gap-2 pb-2">
            <h3 className="text-sm font-semibold">{copy.inBar}</h3>
            <div
              className="flex items-center gap-2 text-xs tabular-nums text-muted-foreground"
              role="status"
            >
              <span className="flex gap-1" aria-hidden="true">
                {Array.from({ length: MAX_BAR_ITEMS }, (_, index) => (
                  <span
                    key={index}
                    className={cn(
                      "h-1.5 w-1.5 rounded-full",
                      index < nav.bar.length
                        ? "bg-foreground"
                        : "bg-muted-foreground/25",
                    )}
                  />
                ))}
              </span>
              {copy.slots
                .replace("{used}", String(nav.bar.length))
                .replace("{max}", String(MAX_BAR_ITEMS))}
            </div>
          </div>
          <Reorder.Group
            axis="y"
            values={nav.bar}
            onReorder={nav.reorderBar}
            className="divide-y divide-border"
          >
            {nav.bar.map(id => (
              <NavRow
                key={id}
                id={id}
                entry={catalog[id]}
                inBar
                atLimit={nav.bar.length <= MIN_BAR_ITEMS}
                move={() => nav.moveToMenu(id)}
                reorder={direction => reorderByKey("bar", id, direction)}
              />
            ))}
          </Reorder.Group>
          <div className="flex min-h-11 items-center gap-2 border-t border-dashed border-border pl-11 text-muted-foreground">
            <MoreVertical className="h-4 w-4" />
            <span className="flex-1 text-sm">{t.common.more}</span>
            <LockKeyhole
              className="mr-3 h-3.5 w-3.5"
              aria-label={copy.fixedMenu}
            />
          </div>
          {nav.bar.length === MIN_BAR_ITEMS && (
            <p className="pt-2 text-xs text-muted-foreground">{copy.minimum}</p>
          )}
        </section>

        <section aria-label={copy.inMenu}>
          <h3 className="pb-2 text-sm font-semibold">{copy.inMenu}</h3>
          <Reorder.Group
            axis="y"
            values={nav.menu}
            onReorder={nav.reorderMenu}
            className="divide-y divide-border"
          >
            {nav.menu.map(id => (
              <NavRow
                key={id}
                id={id}
                entry={catalog[id]}
                inBar={false}
                atLimit={nav.bar.length >= MAX_BAR_ITEMS}
                move={() => nav.moveToBar(id)}
                reorder={direction => reorderByKey("menu", id, direction)}
                remove={
                  catalog[id].group !== "main"
                    ? () => nav.removeShortcut(id)
                    : undefined
                }
              />
            ))}
          </Reorder.Group>
          {nav.bar.length === MAX_BAR_ITEMS && (
            <p className="pt-2 text-xs text-muted-foreground">{copy.maximum}</p>
          )}
        </section>

        {available.length > 0 && (
          <div className="space-y-3">
            <Button
              variant="outline"
              className="w-full border-dashed"
              onClick={() => setPickerOpen(!pickerOpen)}
              aria-expanded={pickerOpen}
              aria-controls="bottom-nav-shortcut-picker"
            >
              {pickerOpen ? (
                <X className="mr-2 h-4 w-4" />
              ) : (
                <Plus className="mr-2 h-4 w-4" />
              )}
              {copy.addShortcut}
            </Button>
            {pickerOpen && (
              <div id="bottom-nav-shortcut-picker" className="space-y-4">
                {(["assets", "money"] as const).map(group => {
                  const ids = available.filter(
                    id => catalog[id].group === group,
                  )
                  if (!ids.length) return null
                  return (
                    <div key={group} className="space-y-2">
                      <h4 className="text-xs font-medium text-muted-foreground">
                        {group === "assets"
                          ? t.common.myAssets
                          : t.management.title}
                      </h4>
                      <div className="grid grid-cols-2 gap-2">
                        {ids.map(id => (
                          <Button
                            key={id}
                            variant="outline"
                            className="h-auto min-h-11 justify-start whitespace-normal px-2 py-2 text-left text-xs"
                            onClick={() => nav.addShortcut(id)}
                            aria-label={copy.add.replace(
                              "{page}",
                              catalog[id].label,
                            )}
                          >
                            {catalog[id].renderIcon("mr-2 h-4 w-4 shrink-0")}
                            <span className="min-w-0 flex-1 break-words">
                              {catalog[id].label}
                            </span>
                            <Plus className="ml-1 h-3 w-3 shrink-0 text-muted-foreground" />
                          </Button>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>
        )}

        {nav.isCustomized && (
          <Button
            variant="ghost"
            size="sm"
            className="text-muted-foreground"
            onClick={nav.reset}
          >
            <RotateCcw className="mr-2 h-4 w-4" />
            {copy.reset}
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
