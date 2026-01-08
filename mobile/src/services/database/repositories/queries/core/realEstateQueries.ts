export enum RealEstateQueries {
  SELECT_FLOWS_BY_REAL_ESTATE_ID = `
        SELECT *
        FROM real_estate_flows ref
            JOIN periodic_flows pf ON ref.periodic_flow_id = pf.id
        WHERE ref.real_estate_id = ?
    `,
  INSERT_FLOW = `
        INSERT INTO real_estate_flows (
            real_estate_id, periodic_flow_id, flow_subtype, description, payload
        ) VALUES (?, ?, ?, ?, ?)
    `,
  INSERT_REAL_ESTATE = `
        INSERT INTO real_estate (
            id, name, photo_url, is_residence, is_rented, bathrooms, bedrooms,
            address, cadastral_reference, purchase_date, purchase_price, currency,
            purchase_expenses, estimated_market_value, annual_appreciation, valuations, rental_data, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `,
  UPDATE_REAL_ESTATE = `
        UPDATE real_estate SET
            name = ?, photo_url = ?, is_residence = ?, is_rented = ?, bathrooms = ?, bedrooms = ?,
            address = ?, cadastral_reference = ?, purchase_date = ?, purchase_price = ?, currency = ?,
            purchase_expenses = ?, estimated_market_value = ?, annual_appreciation = ?, valuations = ?, rental_data = ?,
            updated_at = ?
        WHERE id = ?
    `,
  DELETE_FLOWS_BY_REAL_ESTATE_ID = "DELETE FROM real_estate_flows WHERE real_estate_id = ?",
  DELETE_BY_ID = "DELETE FROM real_estate WHERE id = ?",
  GET_BY_ID = "SELECT * FROM real_estate WHERE id = ?",
  GET_ALL = "SELECT * FROM real_estate ORDER BY name",
}
