import { DatasourceInitiator } from "../ports"
import type { CheckDatasourceExists } from "@/domain/usecases"

export class CheckDatasourceExistsImpl implements CheckDatasourceExists {
  constructor(private datasourceInitiator: DatasourceInitiator) {}

  async execute(): Promise<boolean> {
    return this.datasourceInitiator.exists()
  }
}
