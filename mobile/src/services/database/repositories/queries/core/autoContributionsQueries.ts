export enum AutoContributionsQueries {
  DELETE_BY_ENTITY_AND_SOURCE = "DELETE FROM periodic_contributions WHERE entity_id = ? AND source = ?",
  INSERT_PERIODIC_CONTRIBUTION = `
        INSERT INTO periodic_contributions (
            id, entity_id, target, target_type, target_subtype, alias,
            target_name, amount, currency,
            since, until, frequency, active, is_real, source, created_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  GET_ALL_GROUPED_BY_ENTITY_BASE = `
        SELECT e.id         as entity_id,
               e.name       as entity_name,
               e.natural_id as entity_natural_id,
               e.type       as entity_type,
               e.origin     as entity_origin,
               e.icon_url   as icon_url,
               pc.id        as pc_id,
               pc.*
        FROM periodic_contributions pc
            JOIN entities e ON pc.entity_id = e.id
    `,
  DELETE_BY_SOURCE = "DELETE FROM periodic_contributions WHERE source = ?",
}
