export const normalizeIban = (value: string) =>
  value.replace(/\s/g, "").toUpperCase()

export const isValidExclusionIban = (value: string) =>
  /^[A-Z0-9]{1,34}$/.test(value)
