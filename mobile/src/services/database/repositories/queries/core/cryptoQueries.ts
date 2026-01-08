export enum CryptoAssetQueries {
  GET_BY_SYMBOL = "SELECT * FROM crypto_assets WHERE symbol = ? LIMIT 1",
  INSERT = `
        INSERT INTO crypto_assets (id, name, symbol, icon_urls, external_ids)
        VALUES (?, ?, ?, ?, ?)
    `,
}

export enum CryptoWalletConnectionQueries {
  GET_BY_ENTITY_ID = "SELECT * FROM crypto_wallet_connections WHERE entity_id = ?",
  GET_BY_ENTITY_AND_ADDRESS = "SELECT * FROM crypto_wallet_connections WHERE entity_id = ? AND address = ?",
  GET_CONNECTED_ENTITIES = "SELECT DISTINCT(entity_id) FROM crypto_wallet_connections",
  INSERT = `
        INSERT INTO crypto_wallet_connections (id, entity_id, address, name, created_at)
        VALUES (?, ?, ?, ?, ?)
    `,
  RENAME = `
        UPDATE crypto_wallet_connections
        SET name = ?
        WHERE id = ?
    `,
  DELETE = "DELETE FROM crypto_wallet_connections WHERE id = ?",
}
