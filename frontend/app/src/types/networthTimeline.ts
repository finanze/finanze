export interface NetworthTimelinePoint {
  date: string
  total: number
  breakdown: Record<string, number>
}

export interface NetworthTimeline {
  currency: string
  points: NetworthTimelinePoint[]
}

export interface NetworthTimelineQuery {
  from_date?: string
  to_date?: string
  no_calculation?: boolean
}
