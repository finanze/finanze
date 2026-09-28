function splitFormattedValue(formattedValue: string, locale: string) {
  let decimalSeparator: string | undefined
  try {
    decimalSeparator = new Intl.NumberFormat(locale, {
      minimumFractionDigits: 1,
      maximumFractionDigits: 1,
    })
      .formatToParts(1.1)
      .find(part => part.type === "decimal")?.value
  } catch {
    return null
  }

  if (!decimalSeparator) return null

  const decimalIndex = formattedValue.lastIndexOf(decimalSeparator)
  if (decimalIndex < 0) return null

  const fractionStart = decimalIndex + decimalSeparator.length
  const fractionMatch = formattedValue
    .slice(fractionStart)
    .match(/^\p{Decimal_Number}+/u)
  if (!fractionMatch) return null

  return {
    leading: formattedValue.slice(0, decimalIndex),
    fraction: fractionMatch[0],
    trailing: formattedValue.slice(fractionStart + fractionMatch[0].length),
  }
}

export function FormattedMarketValue({
  value,
  locale,
}: {
  value: string
  locale: string
}) {
  const parts = splitFormattedValue(value, locale)

  if (!parts) {
    return <span className="whitespace-nowrap">{value}</span>
  }

  return (
    <span className="whitespace-nowrap">
      <span className="text-[1.1em]">{parts.leading}</span>
      <span className="inline-block w-[0.15em]" aria-hidden="true" />
      <span className="relative top-[0.08em] align-super text-[0.65em] leading-none">
        {parts.fraction}
      </span>
      {parts.trailing && <span>{parts.trailing}</span>}
    </span>
  )
}
