import { Button } from "@/components/ui/Button"
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
  CardFooter,
} from "@/components/ui/Card"
import { useI18n } from "@/i18n"
import { ImportError, ImportErrorType } from "@/types"

interface ErrorDetailsDialogProps {
  isOpen: boolean
  errors: ImportError[]
  onClose: () => void
}

export function ErrorDetailsDialog({
  isOpen,
  errors,
  onClose,
}: ErrorDetailsDialogProps) {
  const { t } = useI18n()

  if (!isOpen) return null

  const getErrorTypeDisplay = (type: ImportErrorType) => {
    switch (type) {
      case ImportErrorType.SHEET_NOT_FOUND:
        return t.importErrors.sheetNotFound
      case ImportErrorType.MISSING_FIELD:
        return t.importErrors.missingField
      case ImportErrorType.VALIDATION_ERROR:
        return t.importErrors.validationError
      case ImportErrorType.UNEXPECTED_COLUMN:
        return t.importErrors.unexpectedColumn
      default:
        return t.importErrors.unknownError
    }
  }

  const renderErrorDetails = (error: ImportError) => {
    switch (error.type) {
      case ImportErrorType.SHEET_NOT_FOUND:
        return (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            {t.importErrors.sheetNotFoundMessage.replace(
              "{entry}",
              error.entry,
            )}
          </div>
        )

      case ImportErrorType.MISSING_FIELD:
        return (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <div>
              {t.importErrors.missingFieldMessage.replace(
                "{entry}",
                error.entry,
              )}
            </div>
            {error.row && (
              <div className="text-xs text-gray-500 dark:text-gray-500 mb-2">
                {t.importErrors.validationErrorRow.replace(
                  "{row}",
                  error.row.join(", "),
                )}
              </div>
            )}
            <ul className="list-disc list-inside ml-2 mt-1">
              {(error.detail as any[])?.map((field, index) => (
                <li key={index}>
                  {typeof field === "object" &&
                  field !== null &&
                  "field" in field
                    ? field.field
                    : String(field)}
                </li>
              ))}
            </ul>
          </div>
        )

      case ImportErrorType.VALIDATION_ERROR:
        return (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <div>
              {t.importErrors.validationErrorMessage.replace(
                "{entry}",
                error.entry,
              )}
            </div>
            {error.row && (
              <div className="text-xs text-gray-500 dark:text-gray-500 mb-2">
                {t.importErrors.validationErrorRow.replace(
                  "{row}",
                  error.row.join(", "),
                )}
              </div>
            )}
            <ul className="list-disc list-inside ml-2 mt-1">
              {(error.detail as { field: string; value: string }[])?.map(
                (fieldError, index) => (
                  <li key={index}>
                    {t.importErrors.fieldError
                      .replace("{field}", fieldError.field)
                      .replace("{value}", fieldError.value)}
                  </li>
                ),
              )}
            </ul>
          </div>
        )

      case ImportErrorType.UNEXPECTED_COLUMN:
        return (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <div>
              {t.importErrors.unexpectedColumnMessage?.replace(
                "{entry}",
                error.entry,
              )}
            </div>
            {error.row && (
              <div className="text-xs text-gray-500 dark:text-gray-500 mb-2">
                {t.importErrors.validationErrorRow.replace(
                  "{row}",
                  error.row.join(", "),
                )}
              </div>
            )}
            <ul className="list-disc list-inside ml-2 mt-1">
              {(error.detail as string[])?.map((column, index) => (
                <li key={index}>{column}</li>
              ))}
            </ul>
          </div>
        )

      default:
        return (
          <div className="text-sm text-gray-600 dark:text-gray-400">
            <div>
              {t.importErrors.unknownErrorMessage.replace(
                "{entry}",
                error.entry,
              )}
            </div>
            {error.row && (
              <div className="text-xs text-gray-500 dark:text-gray-500 mb-2">
                {t.importErrors.validationErrorRow.replace(
                  "{row}",
                  error.row.join(", "),
                )}
              </div>
            )}
            <ul className="list-disc list-inside ml-2 mt-1">
              {(error.detail as string[])?.map((err, index) => (
                <li key={index}>{err}</li>
              ))}
            </ul>
          </div>
        )
    }
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center p-4 z-50">
      <Card className="w-full max-w-2xl mx-4 max-h-[80vh] flex flex-col">
        <CardHeader className="flex-shrink-0">
          <CardTitle className="text-orange-600 dark:text-orange-400">
            {t.importErrors.title}
          </CardTitle>
        </CardHeader>
        <CardContent className="flex-1 overflow-y-auto min-h-0">
          <div className="mb-4 text-sm text-gray-700 dark:text-gray-300">
            {t.importErrors.description}
          </div>

          <div className="space-y-4">
            {errors
              .filter(error => error.type !== ImportErrorType.UNEXPECTED_COLUMN)
              .map((error, index) => (
                <div
                  key={index}
                  className="border rounded-lg p-3 bg-orange-50 dark:bg-orange-900/20 border-orange-200 dark:border-orange-700"
                >
                  <div className="font-medium text-orange-800 dark:text-orange-200 mb-2">
                    {getErrorTypeDisplay(error.type)}
                  </div>
                  {renderErrorDetails(error)}
                </div>
              ))}
            {errors
              .filter(error => error.type === ImportErrorType.UNEXPECTED_COLUMN)
              .map((error, index) => (
                <div
                  key={`info-${index}`}
                  className="border rounded-lg p-3 bg-gray-50 dark:bg-gray-900/20 border-gray-200 dark:border-gray-700"
                >
                  <div className="font-medium text-gray-800 dark:text-gray-200 mb-2">
                    {getErrorTypeDisplay(error.type)}
                  </div>
                  {renderErrorDetails(error)}
                </div>
              ))}
          </div>
        </CardContent>
        <CardFooter className="flex-shrink-0 flex justify-end">
          <Button onClick={onClose}>{t.common.confirm}</Button>
        </CardFooter>
      </Card>
    </div>
  )
}
