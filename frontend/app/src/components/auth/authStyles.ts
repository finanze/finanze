import { cn } from "@/lib/utils"

export const isLightTheme = (theme: string) =>
  theme === "light" ||
  (theme === "system" &&
    typeof window !== "undefined" &&
    !window.matchMedia("(prefers-color-scheme: dark)").matches)

export const authInputClass = (isLight: boolean) =>
  cn(
    "w-full bg-transparent border-0 border-b rounded-none px-1 py-3 text-base text-center outline-none focus:outline-none focus-visible:outline-none focus-visible:ring-0 focus-visible:ring-offset-0 transition-colors duration-200",
    isLight
      ? "border-black/15 text-black placeholder:text-black/30 focus-visible:border-black/40"
      : "border-white/15 text-white placeholder:text-white/30 focus-visible:border-white/40",
  )

export const authPasswordValueClass =
  "[&:not(:placeholder-shown)]:text-[22px] [&:not(:placeholder-shown)]:tracking-[4px]"
