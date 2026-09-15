import { Component, type ErrorInfo, type ReactNode } from "react"

import { useI18n } from "@/i18n"
import { Button } from "@/components/ui/Button"
import { reportError } from "@/lib/telemetry"

// Restarting on the failing route would just crash again, so land on the root.
function restart() {
  window.location.hash = "#/"
  window.location.reload()
}

function ErrorFallback({
  scope,
  onGoToDashboard,
}: {
  scope: "page" | "app"
  onGoToDashboard: () => void
}) {
  const { t } = useI18n()
  const isApp = scope === "app"

  return (
    <div
      className={`flex w-full flex-col items-center justify-center gap-3 p-8 text-center ${
        isApp ? "min-h-[100svh]" : "min-h-[50vh]"
      }`}
    >
      <h1 className="text-lg font-semibold">{t.errorBoundary.title}</h1>
      <p className="max-w-md text-sm text-muted-foreground">
        {isApp ? t.errorBoundary.description : t.errorBoundary.pageDescription}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-2">
        <Button onClick={onGoToDashboard}>
          {t.errorBoundary.goToDashboard}
        </Button>
        <Button variant="outline" onClick={restart}>
          {t.errorBoundary.restart}
        </Button>
      </div>
    </div>
  )
}

interface Props {
  children: ReactNode
  resetKey?: string
  scope?: "page" | "app"
}

interface State {
  hasError: boolean
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false }

  static getDerivedStateFromError(): State {
    return { hasError: true }
  }

  componentDidUpdate(prevProps: Props) {
    if (this.state.hasError && prevProps.resetKey !== this.props.resetKey) {
      this.setState({ hasError: false })
    }
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled render error:", error, info.componentStack)
    reportError(
      error,
      { phase: "render" },
      {
        component_stack: info.componentStack,
      },
    )
  }

  handleGoToDashboard = () => {
    window.location.hash = "#/"
    this.setState({ hasError: false })
  }

  render() {
    if (this.state.hasError) {
      return (
        <ErrorFallback
          scope={this.props.scope ?? "page"}
          onGoToDashboard={this.handleGoToDashboard}
        />
      )
    }
    return this.props.children
  }
}
