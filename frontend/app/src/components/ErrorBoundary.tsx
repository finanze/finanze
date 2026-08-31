import { Component, type ErrorInfo, type ReactNode } from "react"

import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { reportError } from "@/lib/telemetry"

interface FallbackProps {
  onReload: () => void
}

function ErrorFallback({ onReload }: FallbackProps) {
  const { t } = useI18n()

  return (
    <div className="flex h-screen w-full flex-col items-center justify-center gap-4 p-8 text-center">
      <h1 className="text-lg font-semibold">{t.errorBoundary.title}</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        {t.errorBoundary.description}
      </p>
      <Button onClick={onReload}>{t.errorBoundary.reload}</Button>
    </div>
  )
}

interface Props {
  children: ReactNode
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info.componentStack)
    reportError(error)
  }

  render() {
    if (this.state.hasError) {
      return <ErrorFallback onReload={() => window.location.reload()} />
    }
    return this.props.children
  }
}
