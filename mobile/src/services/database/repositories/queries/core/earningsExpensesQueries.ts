export enum PeriodicFlowsQueries {
  INSERT = `
        INSERT INTO periodic_flows (id, name, amount, currency, flow_type, frequency, category, enabled, since, until, icon, max_amount)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  UPDATE = `
        UPDATE periodic_flows
        SET name = ?, amount = ?, currency = ?, flow_type = ?, frequency = ?, category = ?, enabled = ?, since = ?, until = ?, icon = ?, max_amount = ?
        WHERE id = ?
    `,
  DELETE_BY_ID = "DELETE FROM periodic_flows WHERE id = ?",
  GET_ALL = `
        SELECT f.*, rf.real_estate_id IS NOT NULL AS linked
        FROM periodic_flows f
            LEFT JOIN real_estate_flows rf ON f.id = rf.periodic_flow_id
    `,
  GET_BY_ID = `
        SELECT f.*, rf.real_estate_id IS NOT NULL AS linked
        FROM periodic_flows f
            LEFT JOIN real_estate_flows rf ON f.id = rf.periodic_flow_id
        WHERE id = ?
    `,
}

export enum PendingFlowsQueries {
  INSERT = `
        INSERT INTO pending_flows (id, name, amount, currency, flow_type, category, enabled, date, icon)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  DELETE_ALL = "DELETE FROM pending_flows",
  GET_ALL = "SELECT * FROM pending_flows",
}
