// EVM IDs from https://chainlist.org/rpcs.json; non-EVM chains keep their names.
const CHAIN_ALIASES: Readonly<Record<string, string>> = {
  ethereum: "1",
  optimism: "10",
  bsc: "56",
  "binance-smart-chain": "56",
  gnosis: "100",
  polygon: "137",
  fantom: "250",
  zksync: "324",
  "zksync-era": "324",
  base: "8453",
  arbitrum: "42161",
  avalanche: "43114",
  celo: "42220",
  linea: "59144",
  scroll: "534352",
  blast: "81457",
}

const CHAIN_DISPLAY_NAMES: Readonly<Record<string, string>> = {
  "1": "Ethereum",
  "10": "Optimism",
  "56": "BNB Chain",
  "100": "Gnosis",
  "137": "Polygon",
  "250": "Fantom",
  "324": "zkSync Era",
  "8453": "Base",
  "42161": "Arbitrum",
  "43114": "Avalanche",
  "42220": "Celo",
  "59144": "Linea",
  "534352": "Scroll",
  "81457": "Blast",
  bitcoin: "Bitcoin",
  litecoin: "Litecoin",
  tron: "Tron",
  solana: "Solana",
}

export const normalizeCryptoChain = (
  chain: string | null | undefined,
): string | null => {
  const normalized = chain?.trim().toLowerCase()
  return normalized ? (CHAIN_ALIASES[normalized] ?? normalized) : null
}

export const formatChainName = (chain: string): string => {
  const normalized = normalizeCryptoChain(chain) ?? ""
  return (
    CHAIN_DISPLAY_NAMES[normalized] ??
    normalized
      .split(/[-_\s]+/)
      .filter(Boolean)
      .map(word => word.charAt(0).toUpperCase() + word.slice(1))
      .join(" ")
  )
}
