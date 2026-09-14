import { useState } from "react"
import { Eye, EyeOff } from "lucide-react"
import { Input, type InputProps } from "@/components/ui/Input"
import { useI18n } from "@/i18n"
import { cn } from "@/lib/utils"

export type SecretInputProps = Omit<InputProps, "type">

export function SecretInput({
  className,
  disabled,
  ...props
}: SecretInputProps) {
  const { t } = useI18n()
  const [visible, setVisible] = useState(false)

  return (
    <div className="relative">
      <Input
        type={visible ? "text" : "password"}
        disabled={disabled}
        className={cn("pr-10", className)}
        {...props}
      />
      <button
        type="button"
        className="absolute right-0 top-1/2 -translate-y-1/2 p-2 text-muted-foreground hover:text-foreground transition-colors disabled:opacity-50"
        onClick={() => setVisible(prev => !prev)}
        disabled={disabled}
        aria-label={visible ? t.login.hideCredential : t.login.showCredential}
      >
        {visible ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
      </button>
    </div>
  )
}
