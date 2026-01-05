import { DataManager } from "../dataManager"
import {
  FlowFrequency,
  FlowType,
  PeriodicFlow,
  RealEstate,
  RealEstateFlow,
  RealEstateFlowSubtype,
} from "@/domain"
import { parseDezimalValue } from "@/domain"
import { RealEstatePort } from "@/application/ports"
import { RealEstateQueries } from "./queries"

export class RealEstateRepository implements RealEstatePort {
  constructor(private client: DataManager) {}

  private serializePurchaseExpenses(realEstate: RealEstate): string {
    return JSON.stringify(
      (realEstate.purchaseInfo.expenses ?? []).map(e => ({
        concept: e.concept,
        amount: String(e.amount),
        description: e.description ?? null,
      })),
    )
  }

  private serializeValuations(realEstate: RealEstate): string {
    return JSON.stringify(
      (realEstate.valuationInfo.valuations ?? []).map(v => ({
        date: v.date,
        amount: String(v.amount),
        notes: v.notes ?? null,
      })),
    )
  }

  private serializeRentalData(realEstate: RealEstate): string | null {
    if (!realEstate.rentalData) return null
    const rd = realEstate.rentalData
    return JSON.stringify({
      marginal_tax_rate:
        rd.marginalTaxRate != null ? String(rd.marginalTaxRate) : null,
      vacancy_rate: rd.vacancyRate != null ? String(rd.vacancyRate) : null,
      amortizations: (rd.amortizations ?? []).map(a => ({
        concept: a.concept,
        base_amount: String(a.baseAmount),
        amount: String(a.amount),
        percentage: String(a.percentage),
      })),
    })
  }

  private serializeFlowPayload(flow: RealEstateFlow): string {
    const subtype = flow.flowSubtype
    const payload: any = flow.payload ?? {}

    if (subtype === RealEstateFlowSubtype.LOAN) {
      return JSON.stringify({
        type: payload.type,
        loan_amount:
          payload.loanAmount != null ? String(payload.loanAmount) : null,
        interest_rate:
          payload.interestRate != null ? String(payload.interestRate) : null,
        euribor_rate:
          payload.euriborRate != null ? String(payload.euriborRate) : null,
        interest_type: payload.interestType,
        fixed_years: payload.fixedYears ?? null,
        principal_outstanding:
          payload.principalOutstanding != null
            ? String(payload.principalOutstanding)
            : null,
        monthly_interests:
          payload.monthlyInterests != null
            ? String(payload.monthlyInterests)
            : null,
      })
    }

    if (
      subtype === RealEstateFlowSubtype.COST ||
      subtype === RealEstateFlowSubtype.SUPPLY
    ) {
      return JSON.stringify({ tax_deductible: !!payload.taxDeductible })
    }

    return JSON.stringify({})
  }

  private async tableExists(name: string): Promise<boolean> {
    const res = await this.client.query<{ name: string }>(
      "SELECT name FROM sqlite_master WHERE type='table' AND name = ?",
      [name],
    )
    return res.rows.length > 0
  }

  private mapFlow(flowRow: any): RealEstateFlow {
    const flowSubtype = flowRow.flow_subtype as RealEstateFlowSubtype

    let payloadData: any = {}
    try {
      payloadData = flowRow.payload ? JSON.parse(flowRow.payload) : {}
    } catch {
      payloadData = {}
    }

    const payload: any = (() => {
      if (flowSubtype === RealEstateFlowSubtype.LOAN) {
        return {
          type: payloadData.type,
          loanAmount:
            payloadData.loan_amount != null
              ? parseDezimalValue(payloadData.loan_amount)
              : null,
          interestRate: parseDezimalValue(payloadData.interest_rate),
          euriborRate:
            payloadData.euribor_rate != null
              ? parseDezimalValue(payloadData.euribor_rate)
              : null,
          interestType: payloadData.interest_type,
          fixedYears: payloadData.fixed_years ?? null,
          principalOutstanding: parseDezimalValue(
            payloadData.principal_outstanding,
          ),
          monthlyInterests:
            payloadData.monthly_interests != null
              ? parseDezimalValue(payloadData.monthly_interests)
              : null,
        }
      }
      if (
        flowSubtype === RealEstateFlowSubtype.COST ||
        flowSubtype === RealEstateFlowSubtype.SUPPLY
      ) {
        return {
          taxDeductible: !!payloadData.tax_deductible,
        }
      }
      return {}
    })()

    const periodicFlow: PeriodicFlow = {
      id: flowRow.periodic_flow_id,
      name: flowRow.name,
      amount: parseDezimalValue(flowRow.amount),
      currency: flowRow.currency,
      flowType: flowRow.flow_type as FlowType,
      frequency: flowRow.frequency as FlowFrequency,
      category: flowRow.category ?? null,
      enabled: !!flowRow.enabled,
      since: flowRow.since,
      until: flowRow.until ?? null,
      icon: flowRow.icon ?? null,
      maxAmount:
        flowRow.max_amount != null
          ? parseDezimalValue(flowRow.max_amount)
          : null,
    }

    return {
      periodicFlowId: flowRow.periodic_flow_id,
      periodicFlow,
      flowSubtype,
      description: flowRow.description ?? "",
      payload,
    }
  }

  private mapRealEstate(row: any, flows: RealEstateFlow[]): RealEstate {
    let purchaseExpenses: any[] = []
    try {
      purchaseExpenses = row.purchase_expenses
        ? JSON.parse(row.purchase_expenses)
        : []
    } catch {
      purchaseExpenses = []
    }

    let valuations: any[] = []
    try {
      valuations = row.valuations ? JSON.parse(row.valuations) : []
    } catch {
      valuations = []
    }

    let rentalData: any = null
    try {
      rentalData = row.rental_data ? JSON.parse(row.rental_data) : null
    } catch {
      rentalData = null
    }

    return {
      id: row.id,
      basicInfo: {
        name: row.name,
        isResidence: !!row.is_residence,
        isRented: !!row.is_rented,
        bathrooms: row.bathrooms ?? null,
        bedrooms: row.bedrooms ?? null,
        photoUrl: row.photo_url ?? null,
      },
      location: {
        address: row.address ?? null,
        cadastralReference: row.cadastral_reference ?? null,
      },
      purchaseInfo: {
        date: row.purchase_date,
        price: parseDezimalValue(row.purchase_price),
        expenses: purchaseExpenses.map(e => ({
          concept: e.concept,
          amount: parseDezimalValue(e.amount),
          description: e.description ?? null,
        })),
      },
      valuationInfo: {
        estimatedMarketValue: parseDezimalValue(row.estimated_market_value),
        valuations: valuations.map(v => ({
          date: v.date,
          amount: parseDezimalValue(v.amount),
          notes: v.notes ?? null,
        })),
        annualAppreciation:
          row.annual_appreciation != null
            ? parseDezimalValue(row.annual_appreciation)
            : null,
      },
      flows,
      currency: row.currency,
      rentalData: rentalData
        ? {
            amortizations: Array.isArray(rentalData.amortizations)
              ? rentalData.amortizations.map((a: any) => ({
                  concept: a.concept,
                  baseAmount: parseDezimalValue(a.base_amount ?? 0),
                  amount: parseDezimalValue(a.amount ?? 0),
                  percentage: parseDezimalValue(a.percentage ?? 0),
                }))
              : [],
            marginalTaxRate:
              rentalData.marginal_tax_rate != null
                ? parseDezimalValue(rentalData.marginal_tax_rate)
                : null,
            vacancyRate:
              rentalData.vacancy_rate != null
                ? parseDezimalValue(rentalData.vacancy_rate)
                : null,
          }
        : null,
      createdAt: row.created_at ?? null,
      updatedAt: row.updated_at ?? null,
    }
  }

  async getAll(): Promise<RealEstate[]> {
    const hasRealEstate = await this.tableExists("real_estate")
    if (!hasRealEstate) return []

    const res = await this.client.query<any>(RealEstateQueries.GET_ALL)

    const hasFlows = await this.tableExists("real_estate_flows")
    const hasPeriodicFlows = await this.tableExists("periodic_flows")

    const items: RealEstate[] = []
    for (const row of res.rows) {
      let flows: RealEstateFlow[] = []

      if (hasFlows && hasPeriodicFlows) {
        try {
          const flowRes = await this.client.query<any>(
            RealEstateQueries.SELECT_FLOWS_BY_REAL_ESTATE_ID,
            [row.id],
          )
          flows = flowRes.rows.map(r => this.mapFlow(r))
        } catch {
          flows = []
        }
      }

      items.push(this.mapRealEstate(row, flows))
    }

    return items
  }

  async getById(id: string): Promise<RealEstate | null> {
    const hasRealEstate = await this.tableExists("real_estate")
    if (!hasRealEstate) return null

    const res = await this.client.query<any>(RealEstateQueries.GET_BY_ID, [id])

    if (res.rows.length === 0) return null

    const row = res.rows[0]
    let flows: RealEstateFlow[] = []

    const hasFlows = await this.tableExists("real_estate_flows")
    const hasPeriodicFlows = await this.tableExists("periodic_flows")
    if (hasFlows && hasPeriodicFlows) {
      try {
        const flowRes = await this.client.query<any>(
          RealEstateQueries.SELECT_FLOWS_BY_REAL_ESTATE_ID,
          [row.id],
        )
        flows = flowRes.rows.map(r => this.mapFlow(r))
      } catch {
        flows = []
      }
    }

    return this.mapRealEstate(row, flows)
  }

  async insert(realEstate: RealEstate): Promise<null> {
    const hasRealEstate = await this.tableExists("real_estate")
    if (!hasRealEstate) return null

    const id = realEstate.id
    if (!id) return null

    const hasFlows = await this.tableExists("real_estate_flows")
    const createdAt = new Date().toISOString()

    await this.client.transaction(async () => {
      await this.client.execute(RealEstateQueries.INSERT_REAL_ESTATE, [
        id,
        realEstate.basicInfo.name,
        realEstate.basicInfo.photoUrl ?? null,
        realEstate.basicInfo.isResidence ? 1 : 0,
        realEstate.basicInfo.isRented ? 1 : 0,
        realEstate.basicInfo.bathrooms ?? null,
        realEstate.basicInfo.bedrooms ?? null,
        realEstate.location.address ?? null,
        realEstate.location.cadastralReference ?? null,
        realEstate.purchaseInfo.date,
        String(realEstate.purchaseInfo.price),
        realEstate.currency,
        this.serializePurchaseExpenses(realEstate),
        String(realEstate.valuationInfo.estimatedMarketValue),
        realEstate.valuationInfo.annualAppreciation != null
          ? String(realEstate.valuationInfo.annualAppreciation)
          : null,
        this.serializeValuations(realEstate),
        this.serializeRentalData(realEstate),
        createdAt,
      ])

      if (hasFlows) {
        for (const flow of realEstate.flows ?? []) {
          if (!flow.periodicFlowId) continue
          await this.client.execute(RealEstateQueries.INSERT_FLOW, [
            id,
            flow.periodicFlowId,
            flow.flowSubtype,
            flow.description ?? "",
            this.serializeFlowPayload(flow),
          ])
        }
      }
    })

    return null
  }

  async update(realEstate: RealEstate): Promise<null> {
    const hasRealEstate = await this.tableExists("real_estate")
    if (!hasRealEstate) return null

    const id = realEstate.id
    if (!id) return null

    const hasFlows = await this.tableExists("real_estate_flows")
    const hasPeriodicFlows = await this.tableExists("periodic_flows")
    const updatedAt = new Date().toISOString()

    await this.client.transaction(async () => {
      await this.client.execute(RealEstateQueries.UPDATE_REAL_ESTATE, [
        realEstate.basicInfo.name,
        realEstate.basicInfo.photoUrl ?? null,
        realEstate.basicInfo.isResidence ? 1 : 0,
        realEstate.basicInfo.isRented ? 1 : 0,
        realEstate.basicInfo.bathrooms ?? null,
        realEstate.basicInfo.bedrooms ?? null,
        realEstate.location.address ?? null,
        realEstate.location.cadastralReference ?? null,
        realEstate.purchaseInfo.date,
        String(realEstate.purchaseInfo.price),
        realEstate.currency,
        this.serializePurchaseExpenses(realEstate),
        String(realEstate.valuationInfo.estimatedMarketValue),
        realEstate.valuationInfo.annualAppreciation != null
          ? String(realEstate.valuationInfo.annualAppreciation)
          : null,
        this.serializeValuations(realEstate),
        this.serializeRentalData(realEstate),
        updatedAt,
        id,
      ])

      if (hasFlows) {
        await this.client.execute(
          RealEstateQueries.DELETE_FLOWS_BY_REAL_ESTATE_ID,
          [id],
        )

        if (hasPeriodicFlows) {
          for (const flow of realEstate.flows ?? []) {
            if (!flow.periodicFlowId) continue
            await this.client.execute(RealEstateQueries.INSERT_FLOW, [
              id,
              flow.periodicFlowId,
              flow.flowSubtype,
              flow.description ?? "",
              this.serializeFlowPayload(flow),
            ])
          }
        }
      }
    })

    return null
  }

  async delete(realEstateId: string): Promise<null> {
    const hasRealEstate = await this.tableExists("real_estate")
    if (!hasRealEstate) return null

    const hasFlows = await this.tableExists("real_estate_flows")

    await this.client.transaction(async () => {
      if (hasFlows) {
        await this.client.execute(
          RealEstateQueries.DELETE_FLOWS_BY_REAL_ESTATE_ID,
          [realEstateId],
        )
      }
      await this.client.execute(RealEstateQueries.DELETE_BY_ID, [realEstateId])
    })

    return null
  }
}
