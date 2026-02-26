from enum import Enum


class CryptoAssetQueries(str, Enum):
    GET_BY_SYMBOL = "SELECT * FROM crypto_assets WHERE symbol = ? LIMIT 1"

    UPSERT = """
             INSERT INTO crypto_assets (id, name, symbol, icon_urls, external_ids)
             VALUES (?, ?, ?, ?, ?)
             ON CONFLICT
                 (id)
                 DO UPDATE SET
                name = excluded.name,
                symbol = excluded.symbol,
                icon_urls = excluded.icon_urls,
                external_ids = excluded.external_ids
             """


class CryptoWalletQueries(str, Enum):
    GET_BY_ENTITY_ID = """
       SELECT cw.id,
              cw.entity_id,
              cw.name,
              cw.address_source,
              cw.created_at,
              hdw.xpub,
              hdw.script_type,
              hdw.coin,
              hdw.account,
              json_group_array(
                      cwa.address
              ) as addresses
       FROM crypto_wallets cw
                LEFT JOIN crypto_wallet_addresses cwa ON cw.id = cwa.wallet_id
                LEFT JOIN hd_wallet hdw ON cw.id = hdw.wallet_id
       WHERE cw.entity_id = ?
       GROUP BY cw.id, cw.entity_id, cw.name, cw.address_source, cw.created_at,
                hdw.xpub, hdw.script_type, hdw.coin, hdw.account
    """

    GET_BY_ID = """
       SELECT cw.id,
              cw.entity_id,
              cw.name,
              cw.address_source,
              cw.created_at,
              hdw.xpub,
              hdw.script_type,
              hdw.coin,
              hdw.account,
              json_group_array(
                      cwa.address
              ) as addresses
       FROM crypto_wallets cw
                LEFT JOIN crypto_wallet_addresses cwa ON cw.id = cwa.wallet_id
                LEFT JOIN hd_wallet hdw ON cw.id = hdw.wallet_id
       WHERE cw.id = ?
       GROUP BY cw.id, cw.entity_id, cw.name, cw.address_source, cw.created_at,
                hdw.xpub, hdw.script_type, hdw.coin, hdw.account
    """

    GET_HD_ADDRESSES_BY_WALLET_ID = """
        SELECT 
            address,
            address_index,
            "change",
            derived_path,
            pubkey
        FROM hd_addresses
        WHERE hd_wallet_id = ?
        ORDER BY "change", address_index
    """

    GET_BY_ENTITY_AND_ADDRESS = """
        SELECT 
            cw.*,
            cwa.address as addresses
        FROM crypto_wallets cw
        INNER JOIN crypto_wallet_addresses cwa ON cw.id = cwa.wallet_id
        WHERE cw.entity_id = ? AND cwa.address = ?
        LIMIT 1
    """

    EXISTS_BY_ENTITY_AND_XPUB = """
        SELECT 1
        FROM crypto_wallets cw
        INNER JOIN hd_wallet hdw ON cw.id = hdw.wallet_id
        WHERE cw.entity_id = ? AND hdw.xpub = ?
        LIMIT 1
    """

    GET_CONNECTED_ENTITIES = "SELECT DISTINCT(entity_id) FROM crypto_wallets"

    INSERT = """
        INSERT INTO crypto_wallets (id, entity_id, name, address_source, created_at)
        VALUES (?, ?, ?, ?, ?)
    """

    INSERT_ADDRESS = """
        INSERT INTO crypto_wallet_addresses (wallet_id, address)
        VALUES (?, ?)
    """

    INSERT_HD_WALLET = """
        INSERT INTO hd_wallet (wallet_id, xpub, script_type, coin, account)
        VALUES (?, ?, ?, ?, ?)
    """

    RENAME = """
        UPDATE crypto_wallets
        SET name = ?
        WHERE id = ?
    """

    DELETE = "DELETE FROM crypto_wallets WHERE id = ?"
