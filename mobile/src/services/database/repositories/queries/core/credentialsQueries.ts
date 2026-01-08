export enum CredentialQueries {
  GET_BY_ENTITY = `
        SELECT credentials
        FROM entity_credentials
        WHERE entity_id = ?
    `,
  GET_ALL = "SELECT * FROM entity_credentials",
  INSERT = `
        INSERT INTO entity_credentials (entity_id, credentials, last_used_at, created_at)
        VALUES (?, ?, ?, ?)
    `,
  DELETE_BY_ENTITY = "DELETE FROM entity_credentials WHERE entity_id = ?",
  UPDATE_LAST_USED_AT = `
        UPDATE entity_credentials
        SET last_used_at = ?
        WHERE entity_id = ?
    `,
  UPDATE_EXPIRATION = `
        UPDATE entity_credentials
        SET expiration = ?
        WHERE entity_id = ?
    `,
}
