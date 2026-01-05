import { DatasourceInitiator } from "../ports"
import type { InitializeDatasource } from "@/domain/usecases"

export class InitializeDatasourceImpl implements InitializeDatasource {
  constructor(private datasourceInitiator: DatasourceInitiator) {}

  async execute(password: string): Promise<void> {
    await this.datasourceInitiator.initialize(password)
  }
}
