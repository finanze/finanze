import {
  EntitiesPosition,
  ProductType,
  PositionQueryRequest,
  GlobalPosition,
} from "@/domain"
import { PositionPort, EntityPort } from "../ports"
import { GetPosition } from "@/domain/usecases"

function daysInMonth(year: number, monthZeroBased: number): number {
  return new Date(year, monthZeroBased + 1, 0).getDate()
}

function formatLocalDate(date: Date): string {
  const y = date.getFullYear()
  const m = String(date.getMonth() + 1).padStart(2, "0")
  const d = String(date.getDate()).padStart(2, "0")
  return `${y}-${m}-${d}`
}

function calculateNextLoanPaymentDate(): string {
  // Backend uses: today + relativedelta(months=1), then keeps today's day.
  // We clamp the day to the target month length to avoid invalid dates.
  const today = new Date()
  today.setHours(0, 0, 0, 0)

  const targetYear = today.getFullYear()
  const targetMonth = today.getMonth() + 1

  const nextMonthDate = new Date(targetYear, targetMonth, 1)
  const dim = daysInMonth(nextMonthDate.getFullYear(), nextMonthDate.getMonth())
  const day = Math.min(today.getDate(), dim)

  const next = new Date(
    nextMonthDate.getFullYear(),
    nextMonthDate.getMonth(),
    day,
  )
  return formatLocalDate(next)
}

function enrichLoans(position: any): void {
  if (!position.products || !(ProductType.LOAN in position.products)) {
    return
  }

  const loans = position.products[ProductType.LOAN]
  if (!loans?.entries) {
    return
  }

  for (const loan of loans.entries) {
    if (loan.nextPaymentDate == null) {
      loan.nextPaymentDate = calculateNextLoanPaymentDate()
    }
  }
}

function enrichData(data: Record<string, GlobalPosition>): void {
  for (const [entityId, position] of Object.entries(data)) {
    if (position == null) continue
    enrichLoans(position)
  }
}

export class GetPositionImpl implements GetPosition {
  constructor(
    private positionPort: PositionPort,
    private entityPort: EntityPort,
  ) {}

  async execute(query?: PositionQueryRequest): Promise<EntitiesPosition> {
    const disabledEntities = await this.entityPort.getDisabledEntities()
    const excludedEntities = disabledEntities
      .map(e => e.id)
      .filter((id): id is string => Boolean(id))

    const fullQuery: PositionQueryRequest = {
      entities: query?.entities,
      excludedEntities,
    }

    const positionsDataByEntity =
      await this.positionPort.getLastGroupedByEntity(fullQuery)

    const positionsData: Record<string, GlobalPosition> = {}
    for (const [entity, position] of positionsDataByEntity.entries()) {
      if (entity.id) {
        positionsData[entity.id] = position
      }
    }

    enrichData(positionsData)

    return { positions: positionsData }
  }
}
