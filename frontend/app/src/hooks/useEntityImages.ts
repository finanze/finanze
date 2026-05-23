import { useState, useEffect } from "react"
import { EntityOrigin } from "@/types"
import { getImageUrl } from "@/services/api"

interface EntityIconSource {
  id: string
  origin: EntityOrigin
  icon_url?: string | null
}

export function useEntityImages(
  entities: EntityIconSource[],
): Record<string, string> {
  const [images, setImages] = useState<Record<string, string>>({})

  useEffect(() => {
    const loadImages = async () => {
      const result: Record<string, string> = {}
      for (const entity of entities) {
        try {
          if (entity.icon_url) {
            result[entity.id] = entity.icon_url
          } else if (entity.origin === EntityOrigin.EXTERNALLY_PROVIDED) {
            result[entity.id] = await getImageUrl(
              `/static/entities/logos/${entity.id}.png`,
            )
          } else if (entity.origin === EntityOrigin.NATIVE) {
            result[entity.id] = `entities/${entity.id}.png`
          } else {
            result[entity.id] = ""
          }
        } catch {
          result[entity.id] = ""
        }
      }
      setImages(result)
    }
    loadImages()
  }, [entities])

  return images
}
