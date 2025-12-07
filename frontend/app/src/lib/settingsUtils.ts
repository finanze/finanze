export const cleanObject = (obj: any): any => {
  if (obj === null || obj === undefined) {
    return undefined
  }

  if (Array.isArray(obj)) {
    if (obj.length === 0) {
      return undefined
    }
    const cleanedArray = obj
      .map(item => cleanObject(item))
      .filter(item => item !== undefined)
    return cleanedArray.length > 0 ? cleanedArray : undefined
  }

  if (typeof obj === "object") {
    const cleanedObj: Record<string, any> = {}
    let hasValues = false

    for (const [key, value] of Object.entries(obj)) {
      const cleanedValue = cleanObject(value)
      if (cleanedValue !== undefined) {
        cleanedObj[key] = cleanedValue
        hasValues = true
      }
    }

    return hasValues ? cleanedObj : undefined
  }

  if (obj === null || obj === "") {
    return undefined
  }

  return obj
}

export const processDataFields = (settingsObj: any) => {
  const processed = { ...settingsObj }

  if (processed.export?.sheets) {
    Object.entries(processed.export.sheets).forEach(([section, items]) => {
      if (section !== "globals" && Array.isArray(items)) {
        ;(items as any[]).forEach(item => {
          if (
            section !== "position" &&
            item.data &&
            typeof item.data === "string"
          ) {
            if (item.data.includes(",")) {
              item.data = item.data
                .split(",")
                .map((v: string) => v.trim())
                .filter((v: string) => v !== "")
            } else if (item.data.trim() !== "") {
              item.data = [item.data.trim()]
            } else {
              item.data = []
            }
          }

          if (item.filters && Array.isArray(item.filters)) {
            item.filters.forEach((filter: any) => {
              if (filter.values && typeof filter.values === "string") {
                if (filter.values.includes(",")) {
                  filter.values = filter.values
                    .split(",")
                    .map((v: string) => v.trim())
                    .filter((v: string) => v !== "")
                } else if (filter.values.trim() !== "") {
                  filter.values = [filter.values.trim()]
                } else {
                  filter.values = []
                }
              }
            })
          }
        })
      }
    })
  }

  if (processed.importing?.sheets) {
    Object.entries(processed.importing.sheets).forEach(([section, items]) => {
      if (section !== "globals" && Array.isArray(items)) {
        ;(items as any[]).forEach(item => {
          // For import, keep data as a single string value (don't convert to array)
          // The data field should remain as-is (string or null)

          if (item.filters && Array.isArray(item.filters)) {
            item.filters.forEach((filter: any) => {
              if (filter.values && typeof filter.values === "string") {
                if (filter.values.includes(",")) {
                  filter.values = filter.values
                    .split(",")
                    .map((v: string) => v.trim())
                    .filter((v: string) => v !== "")
                } else if (filter.values.trim() !== "") {
                  filter.values = [filter.values.trim()]
                } else {
                  filter.values = []
                }
              }
            })
          }
        })
      }
    })
  }

  return processed
}

export const sanitizeStablecoins = (stablecoins: string[] | undefined) =>
  Array.from(
    new Set((stablecoins ?? []).map(symbol => symbol.trim().toUpperCase())),
  ).filter(Boolean)
