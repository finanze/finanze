export enum TemplateQueries {
  INSERT = `
        INSERT INTO templates (id, name, feature, type, fields, products, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    `,
  UPDATE = `
        UPDATE templates
        SET name = ?, feature = ?, type = ?, fields = ?, products = ?, updated_at = ?
        WHERE id = ?
    `,
  DELETE_BY_ID = "DELETE FROM templates WHERE id = ?",
  GET_BY_ID = "SELECT * FROM templates WHERE id = ?",
  GET_BY_TYPE = "SELECT * FROM templates WHERE type = ?",
  GET_BY_NAME_AND_TYPE = "SELECT * FROM templates WHERE name = ? AND type = ?",
}
