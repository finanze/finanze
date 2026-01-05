import { CloudSession } from "../cloudAuth"

export interface GetAuthSession {
  execute(): Promise<CloudSession | null>
}
