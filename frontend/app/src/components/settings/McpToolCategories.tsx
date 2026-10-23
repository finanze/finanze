import { useId, useState } from "react"
import { Check, ChevronRight, Info, LockKeyhole, RotateCcw } from "lucide-react"
import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { Switch } from "@/components/ui/Switch"
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/Popover"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"
import type {
  McpCategoryPreferences,
  McpConfig,
  McpToolCatalog,
} from "@/types/mcp"

interface McpToolCategoriesProps {
  config: McpConfig
  catalog: McpToolCatalog
  isSaving: boolean
  onChange: (preferences: McpCategoryPreferences) => void
}

const DEFAULT_ACCESS = { read_enabled: true, write_enabled: true }

function ToolNamesPopover({
  label,
  names,
}: {
  label: string
  names: string[]
}) {
  return (
    <Popover>
      <Tooltip>
        <TooltipTrigger asChild>
          <PopoverTrigger asChild>
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="h-7 w-7 shrink-0 text-muted-foreground"
              aria-label={label}
            >
              <Info className="h-3.5 w-3.5" aria-hidden="true" />
            </Button>
          </PopoverTrigger>
        </TooltipTrigger>
        <TooltipContent className="max-w-64 text-center">
          {label}
        </TooltipContent>
      </Tooltip>
      <PopoverContent
        align="end"
        collisionPadding={16}
        aria-label={label}
        className="w-80 max-w-[calc(100vw-2rem)] p-3"
      >
        <h4 className="break-words text-sm font-medium">{label}</h4>
        <ul className="mt-2 max-h-64 space-y-1 overflow-y-auto">
          {names.map(name => (
            <li key={name}>
              <code className="block break-all font-mono text-xs leading-5">
                {name}
              </code>
            </li>
          ))}
        </ul>
      </PopoverContent>
    </Popover>
  )
}

export function McpToolCategories({
  config,
  catalog,
  isSaving,
  onChange,
}: McpToolCategoriesProps) {
  const { t } = useI18n()
  const text = t.settings.mcp.toolCategories
  const [expanded, setExpanded] = useState(false)
  const contentId = useId()
  const disabled = isSaving || !config.enabled
  const total = catalog.tool_categories.reduce(
    (count, category) => count + category.read_count + category.write_count,
    catalog.essential_count,
  )
  const active = !config.enabled
    ? 0
    : catalog.tool_categories.reduce((count, category) => {
        const access = config.category_access[category.id] ?? DEFAULT_ACCESS
        if (!access.read_enabled) return count
        return (
          count +
          category.read_count +
          (!config.read_only && access.write_enabled ? category.write_count : 0)
        )
      }, catalog.essential_count)
  const hasChanges = catalog.tool_categories.some(({ id }) => {
    const access = config.category_access[id] ?? DEFAULT_ACCESS
    return !access.read_enabled || !access.write_enabled
  })

  return (
    <div className="border-t pt-3">
      <button
        type="button"
        className="flex w-full items-center gap-2 rounded-sm py-2 text-left text-sm font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2"
        aria-label={text.title}
        aria-expanded={expanded}
        aria-controls={contentId}
        data-testid="mcp-tool-categories"
        onClick={() => setExpanded(!expanded)}
      >
        <ChevronRight
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 ${expanded ? "rotate-90" : ""}`}
        />
        <span className="min-w-0 flex-1 break-words">{text.title}</span>
        <span
          role="status"
          aria-live="polite"
          data-testid="mcp-tool-count"
          className="shrink-0 text-xs font-normal tabular-nums text-muted-foreground"
        >
          {text.activeCount
            .replace("{active}", String(active))
            .replace("{total}", String(total))}
        </span>
      </button>
      {expanded && (
        <div id={contentId} className="pt-3">
          <TooltipProvider>
            <table className="w-full table-fixed text-sm">
              <caption className="sr-only">{text.title}</caption>
              <colgroup>
                <col />
                <col className="w-20" />
                <col className="w-20" />
              </colgroup>
              <thead>
                <tr className="border-b text-xs text-muted-foreground">
                  <th scope="col" className="pb-3 text-left font-medium">
                    {text.category}
                  </th>
                  <th scope="col" className="pb-3 text-center font-medium">
                    {text.read}
                  </th>
                  <th scope="col" className="pb-3 text-center font-medium">
                    {text.write}
                  </th>
                </tr>
              </thead>
              <tbody className="divide-y">
                <tr>
                  <th scope="row" className="py-3 pr-2 text-left font-normal">
                    <span className="flex items-center gap-2">
                      {text.essential}
                      <Tooltip>
                        <TooltipTrigger asChild>
                          <span
                            tabIndex={0}
                            aria-label={text.essentialLocked}
                            className="inline-flex shrink-0 text-muted-foreground"
                          >
                            <LockKeyhole
                              className="h-3.5 w-3.5"
                              aria-hidden="true"
                            />
                          </span>
                        </TooltipTrigger>
                        <TooltipContent className="max-w-64 text-center">
                          {text.essentialLocked}
                        </TooltipContent>
                      </Tooltip>
                    </span>
                    <span className="mt-0.5 block text-xs tabular-nums text-muted-foreground">
                      {text.toolCount.replace(
                        "{count}",
                        String(catalog.essential_count),
                      )}
                    </span>
                  </th>
                  <td className="text-center">
                    <div className="flex items-center justify-center gap-1">
                      <span className="inline-flex w-9 justify-center">
                        <Check
                          className="h-4 w-4 text-muted-foreground"
                          aria-label={text.essentialLocked}
                        />
                      </span>
                      <ToolNamesPopover
                        label={text.readTools.replace(
                          "{category}",
                          text.essential,
                        )}
                        names={catalog.essential_tools}
                      />
                    </div>
                  </td>
                  <td className="text-center text-muted-foreground">-</td>
                </tr>
                {catalog.tool_categories.map(category => {
                  const access =
                    config.category_access[category.id] ?? DEFAULT_ACCESS
                  const name = text.names[category.id]
                  const paused = config.read_only && category.write_count > 0
                  return (
                    <tr
                      key={category.id}
                      data-testid={`mcp-category-${category.id}`}
                    >
                      <th
                        scope="row"
                        className="break-words py-3 pr-2 text-left font-normal"
                      >
                        {name}
                        <span className="mt-0.5 block text-xs tabular-nums text-muted-foreground">
                          {text.toolCount.replace(
                            "{count}",
                            String(category.read_count + category.write_count),
                          )}
                        </span>
                      </th>
                      <td className="text-center">
                        <div className="flex items-center justify-center gap-1">
                          <Switch
                            size="sm"
                            aria-label={text.readAccess.replace(
                              "{category}",
                              name,
                            )}
                            data-testid={`mcp-category-${category.id}-read`}
                            checked={access.read_enabled}
                            disabled={disabled}
                            onCheckedChange={checked =>
                              onChange({
                                [category.id]: {
                                  read_enabled: checked,
                                  write_enabled:
                                    checked && access.write_enabled,
                                },
                              })
                            }
                          />
                          <ToolNamesPopover
                            label={text.readTools.replace("{category}", name)}
                            names={category.read_tools}
                          />
                        </div>
                      </td>
                      <td className="text-center">
                        {category.write_count === 0 ? (
                          <span className="text-muted-foreground">-</span>
                        ) : (
                          <div className="flex items-center justify-center gap-1">
                            <Tooltip>
                              <TooltipTrigger asChild>
                                <span
                                  className="inline-flex items-center"
                                  tabIndex={paused ? 0 : undefined}
                                  aria-label={
                                    paused ? text.writesPaused : undefined
                                  }
                                >
                                  <Switch
                                    size="sm"
                                    aria-label={text.writeAccess.replace(
                                      "{category}",
                                      name,
                                    )}
                                    data-testid={`mcp-category-${category.id}-write`}
                                    checked={access.write_enabled}
                                    disabled={disabled || config.read_only}
                                    onCheckedChange={checked =>
                                      onChange({
                                        [category.id]: {
                                          read_enabled:
                                            checked || access.read_enabled,
                                          write_enabled: checked,
                                        },
                                      })
                                    }
                                  />
                                </span>
                              </TooltipTrigger>
                              {paused && (
                                <TooltipContent className="max-w-64 text-center">
                                  {text.writesPaused}
                                </TooltipContent>
                              )}
                            </Tooltip>
                            <ToolNamesPopover
                              label={text.writeTools.replace(
                                "{category}",
                                name,
                              )}
                              names={category.write_tools}
                            />
                          </div>
                        )}
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </TooltipProvider>
          <div className="flex justify-end border-t pt-3">
            <Button
              type="button"
              size="sm"
              variant="ghost"
              disabled={disabled || !hasChanges}
              data-testid="mcp-categories-reset"
              onClick={() =>
                onChange(
                  Object.fromEntries(
                    catalog.tool_categories.map(({ id }) => [
                      id,
                      { ...DEFAULT_ACCESS },
                    ]),
                  ),
                )
              }
            >
              <RotateCcw className="mr-2 h-3.5 w-3.5" aria-hidden="true" />
              {text.restoreDefaults}
            </Button>
          </div>
        </div>
      )}
    </div>
  )
}
