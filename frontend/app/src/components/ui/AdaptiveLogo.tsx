import { useEffect, useState } from "react"

import { cn } from "@/lib/utils"
import { isMostlyBlackLogo } from "@/utils/iconAnalysis"

interface AdaptiveLogoProps {
  src: string
  alt: string
  className?: string
  imgClassName?: string
  fallbackSrc?: string
  lightBgClassName?: string
}

/**
 * Renders a logo and, when the artwork is almost entirely black (e.g. black
 * lettering on a transparent background), places it on a rounded white surface
 * so it stays legible on dark backgrounds. Colors are never inverted, so brand
 * palettes are preserved.
 */
export function AdaptiveLogo({
  src,
  alt,
  className,
  imgClassName,
  fallbackSrc,
  lightBgClassName = "bg-white",
}: AdaptiveLogoProps) {
  const [currentSrc, setCurrentSrc] = useState(src)
  const [useCors, setUseCors] = useState(true)
  const [needsLightBg, setNeedsLightBg] = useState(false)

  useEffect(() => {
    setCurrentSrc(src)
    setUseCors(true)
    setNeedsLightBg(false)
  }, [src])

  return (
    <div className={cn(className, needsLightBg && lightBgClassName)}>
      <img
        src={currentSrc}
        alt={alt}
        crossOrigin={useCors ? "anonymous" : undefined}
        className={imgClassName}
        onLoad={event => {
          const image = event.currentTarget
          if (image.naturalWidth === 0) return
          try {
            if (isMostlyBlackLogo(image)) setNeedsLightBg(true)
          } catch {
            // Cross-origin image without CORS headers taints the canvas; skip.
          }
        }}
        onError={() => {
          if (useCors) {
            // Retry without CORS: the logo loads but blackness can't be sampled.
            setUseCors(false)
            return
          }
          if (fallbackSrc && currentSrc !== fallbackSrc) {
            setCurrentSrc(fallbackSrc)
            setNeedsLightBg(false)
          }
        }}
      />
    </div>
  )
}
