export enum ExternalIntegrationQueries {
  DEACTIVATE = `
        UPDATE external_integrations
        SET status  = ?,
            payload = NULL
        WHERE id = ?
    `,
  ACTIVATE = `
        UPDATE external_integrations
        SET status  = ?,
            payload = ?
        WHERE id = ?
    `,
  GET_PAYLOAD = "SELECT payload FROM external_integrations WHERE id = ? AND status = ? AND payload IS NOT NULL",
  GET_PAYLOADS_BY_TYPE = `
        SELECT id, payload
        FROM external_integrations
        WHERE type = ?
          AND status = ?
          AND payload IS NOT NULL
    `,
  GET_ALL = `
        SELECT id, name, type, status
        FROM external_integrations
    `,
}
