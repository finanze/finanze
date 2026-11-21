import type { Page } from "@playwright/test";
import { execFileSync } from "node:child_process";
import { randomUUID } from "node:crypto";
import { mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { createServer, type IncomingMessage, type Server } from "node:http";
import type { AddressInfo } from "node:net";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { PROJECT_ROOT, PYTHON_BIN, PYTHON_PATH } from "../fixtures/backend";

export interface StoredBackupPiece {
  id: string;
  protocol: number;
  date: string;
  type: "DATA" | "CONFIG";
  size: number;
  schema_revision?: number;
  schema_hash?: string;
  payload: Buffer;
}

export type PayloadMutationMode =
  | "ahead_of_time"
  | "mid_upgrade_failure"
  | "backdate_last_update";

export interface CloudBackupMockServer {
  url: string;
  getDataPiece: () => StoredBackupPiece | null;
  setDataPiece: (piece: StoredBackupPiece) => Promise<void>;
  restoreDataPieceAsNewer: (
    piece: StoredBackupPiece,
    overrides?: Partial<Omit<StoredBackupPiece, "payload" | "size">>,
  ) => Promise<StoredBackupPiece>;
  mutateDataPieceWithPython: (params: {
    basePayload: Buffer;
    password: string;
    mode: Exclude<PayloadMutationMode, "backdate_last_update">;
    schema_revision?: number;
  }) => Promise<StoredBackupPiece>;
  createBackdatedBackupPiece: (params: {
    piece: StoredBackupPiece;
    password: string;
    date: string;
  }) => StoredBackupPiece;
  clear: () => Promise<void>;
  close: () => Promise<void>;
}

const PYTHON_MUTATE_SCRIPT = `
import hashlib
import sqlite3
import sys
from pathlib import Path

from domain.backup import BackupFileType, BackupProcessRequest
from infrastructure.cloud.backup.backup_processor_adapter import BackupProcessorV1

payload_path = Path(sys.argv[1])
db_path = Path(sys.argv[2])
password = sys.argv[3]
mode = sys.argv[4]
extra_arg = sys.argv[5] if len(sys.argv) > 5 else ""

hashed_pw = hashlib.sha3_256(password.encode("utf-8")).hexdigest()
processor = BackupProcessorV1()
decompiled = processor.decompile(
    BackupProcessRequest(
        protocol=1,
        password=hashed_pw,
        type=BackupFileType.DATA,
        payload=payload_path.read_bytes(),
    )
)
db_path.write_bytes(decompiled.payload)

conn = sqlite3.connect(str(db_path))
try:
    if mode == "ahead_of_time":
        conn.execute(
            "INSERT INTO migrations (version, applied_at, name) VALUES (9999, '2099-01-01T00:00:00+00:00', 'v99.0.0:0_future_migration')"
        )
    elif mode == "mid_upgrade_failure":
        conn.execute(
            "DELETE FROM migrations WHERE version = (SELECT MAX(version) FROM migrations)"
        )
        conn.execute(
            "CREATE TRIGGER fail_upgrade BEFORE INSERT ON migrations BEGIN SELECT RAISE(ABORT, 'simulated mid-upgrade failure'); END"
        )
    elif mode == "backdate_last_update":
        conn.execute(
            'UPDATE sys_config SET value = ? WHERE "key" = ?',
            (extra_arg, "last_update"),
        )
    else:
        raise ValueError(f"Unknown mode: {mode}")
    conn.commit()
finally:
    conn.close()

compiled = processor.compile(
    BackupProcessRequest(
        protocol=1,
        password=hashed_pw,
        type=BackupFileType.DATA,
        payload=db_path.read_bytes(),
    )
)
payload_path.write_bytes(compiled.payload)
`;

function readBuffer(request: IncomingMessage): Promise<Buffer> {
  return new Promise((resolve, reject) => {
    const chunks: Buffer[] = [];
    request.on("data", (chunk) => chunks.push(Buffer.from(chunk)));
    request.on("end", () => resolve(Buffer.concat(chunks)));
    request.on("error", reject);
  });
}

function serializePieceMeta(piece: StoredBackupPiece) {
  return {
    id: piece.id,
    protocol: piece.protocol,
    date: piece.date,
    type: piece.type,
    size: piece.size,
    ...(piece.schema_revision !== undefined ? { schema_revision: piece.schema_revision } : {}),
    ...(piece.schema_hash !== undefined ? { schema_hash: piece.schema_hash } : {}),
  };
}

async function waitForBackendInfoCacheExpiry(): Promise<void> {
  await new Promise((r) => setTimeout(r, 1_150));
}

function mutateEncryptedPayload(
  basePayload: Buffer,
  password: string,
  mode: PayloadMutationMode,
  extraArg = "",
): Buffer {
  const workDir = mkdtempSync(join(tmpdir(), "finanze-e2e-mutate-"));
  try {
    const payloadPath = join(workDir, "backup.bin");
    const dbPath = join(workDir, "backup.sqlite");
    writeFileSync(payloadPath, basePayload);

    execFileSync(
      PYTHON_BIN,
      [
        "-c",
        PYTHON_MUTATE_SCRIPT,
        payloadPath,
        dbPath,
        password,
        mode,
        extraArg,
      ],
      {
        cwd: PROJECT_ROOT,
        env: {
          ...process.env,
          PYTHONPATH: PYTHON_PATH,
        },
        stdio: "pipe",
      },
    );

    return readFileSync(payloadPath);
  } finally {
    rmSync(workDir, {
      recursive: true,
      force: true,
      maxRetries: 5,
      retryDelay: 100,
    });
  }
}

export async function startCloudBackupMockServer(): Promise<CloudBackupMockServer> {
  const pieces = new Map<string, StoredBackupPiece>();
  const stagedUploads = new Map<string, Omit<StoredBackupPiece, "payload">>();
  let baseUrl = "";

  const server: Server = createServer(async (request, response) => {
    const sendJson = (status: number, body: unknown) => {
      response.writeHead(status, { "Content-Type": "application/json" });
      response.end(JSON.stringify(body));
    };

    const parsedUrl = new URL(request.url ?? "/", "http://127.0.0.1");
    const { pathname, searchParams } = parsedUrl;

    if (request.method === "GET" && pathname === "/v1/backups") {
      const out: Record<string, ReturnType<typeof serializePieceMeta>> = {};
      for (const [type, piece] of pieces.entries()) {
        out[type] = serializePieceMeta(piece);
      }
      return sendJson(200, { pieces: out });
    }

    if (request.method === "POST" && pathname === "/v1/backups/upload") {
      const raw = await readBuffer(request);
      const body = JSON.parse(raw.toString() || "{}") as {
        pieces?: Array<{
          id: string;
          type: "DATA" | "CONFIG";
          size: number;
          date: string;
          protocol: number;
          schema_revision?: number;
          schema_hash?: string;
        }>;
      };
      const uploads = (body.pieces ?? []).map((piece) => {
        const token = randomUUID();
        stagedUploads.set(token, {
          id: piece.id,
          type: piece.type,
          size: piece.size,
          date: piece.date,
          protocol: piece.protocol,
          ...(piece.schema_revision !== undefined ? { schema_revision: piece.schema_revision } : {}),
          ...(piece.schema_hash !== undefined ? { schema_hash: piece.schema_hash } : {}),
        });
        const headers: Record<string, string> = {
          "Content-Type": "application/octet-stream",
          "x-amz-meta-id": piece.id,
          "x-amz-meta-protocol": String(piece.protocol),
          "x-amz-meta-date": piece.date,
          "x-amz-meta-type": piece.type,
        };
        if (piece.schema_revision !== undefined) {
          headers["x-amz-meta-schema_revision"] = String(piece.schema_revision);
        }
        if (piece.schema_hash !== undefined) {
          headers["x-amz-meta-schema_hash"] = piece.schema_hash;
        }
        return {
          type: piece.type,
          method: "PUT",
          url: `${baseUrl}/r2/${piece.type}?token=${token}`,
          headers,
        };
      });
      return sendJson(200, { uploads });
    }

    if (request.method === "PUT" && pathname.startsWith("/r2/")) {
      const token = searchParams.get("token") ?? "";
      const staged = stagedUploads.get(token);
      if (!staged) {
        return sendJson(400, { error: "Invalid upload token" });
      }
      const payload = await readBuffer(request);
      stagedUploads.delete(token);
      const rawHeaderRevision = request.headers["x-amz-meta-schema_revision"];
      const parsedRevision =
        typeof rawHeaderRevision === "string"
          ? Number.parseInt(rawHeaderRevision, 10)
          : staged.schema_revision;
      const rawHeaderHash = request.headers["x-amz-meta-schema_hash"];
      const parsedHash =
        typeof rawHeaderHash === "string" ? rawHeaderHash : staged.schema_hash;
      pieces.set(staged.type, {
        ...staged,
        size: payload.length,
        ...(parsedRevision !== undefined && !Number.isNaN(parsedRevision)
          ? { schema_revision: parsedRevision }
          : {}),
        ...(parsedHash !== undefined ? { schema_hash: parsedHash } : {}),
        payload,
      });
      response.writeHead(200);
      response.end();
      return;
    }

    if (request.method === "GET" && pathname === "/v1/backups/download") {
      const requestedTypes = searchParams.getAll("type");
      const out: Record<
        string,
        ReturnType<typeof serializePieceMeta> & { url: string }
      > = {};
      for (const type of requestedTypes) {
        const piece = pieces.get(type);
        if (!piece) continue;
        out[type] = {
          ...serializePieceMeta(piece),
          url: `${baseUrl}/r2/${type}`,
        };
      }
      return sendJson(200, { pieces: out });
    }

    if (request.method === "GET" && pathname.startsWith("/r2/")) {
      const type = pathname.slice("/r2/".length);
      const piece = pieces.get(type);
      if (!piece) {
        return sendJson(404, { error: "Piece not found" });
      }
      response.writeHead(200, {
        "Content-Type": "application/octet-stream",
        "Content-Length": String(piece.payload.length),
      });
      response.end(piece.payload);
      return;
    }

    sendJson(404, { error: "Not found" });
  });

  await new Promise<void>((resolve) => server.listen(0, "127.0.0.1", resolve));
  const { port } = server.address() as AddressInfo;
  baseUrl = `http://127.0.0.1:${port}`;

  let bumpCounter = 1;
  const nextFutureIsoDate = (fromIso?: string) => {
    const baseMs = Math.max(Date.now(), fromIso ? Date.parse(fromIso) : 0);
    bumpCounter += 1;
    return new Date(baseMs + bumpCounter * 60_000).toISOString();
  };

  return {
    url: baseUrl,
    getDataPiece: () => {
      const piece = pieces.get("DATA");
      return piece ? { ...piece, payload: Buffer.from(piece.payload) } : null;
    },
    setDataPiece: async (piece) => {
      pieces.set("DATA", {
        ...piece,
        size: piece.payload.length,
        payload: Buffer.from(piece.payload),
      });
      await waitForBackendInfoCacheExpiry();
    },
    restoreDataPieceAsNewer: async (piece, overrides = {}) => {
      const current = pieces.get("DATA");
      const updated: StoredBackupPiece = {
        id: overrides.id ?? randomUUID(),
        protocol: overrides.protocol ?? piece.protocol,
        date: overrides.date ?? nextFutureIsoDate(current?.date ?? piece.date),
        type: "DATA",
        size: piece.payload.length,
        ...(overrides.schema_revision !== undefined
          ? { schema_revision: overrides.schema_revision }
          : piece.schema_revision !== undefined
            ? { schema_revision: piece.schema_revision }
            : {}),
        ...(overrides.schema_hash !== undefined
          ? { schema_hash: overrides.schema_hash }
          : piece.schema_hash !== undefined
            ? { schema_hash: piece.schema_hash }
            : {}),
        payload: Buffer.from(piece.payload),
      };
      pieces.set("DATA", updated);
      await waitForBackendInfoCacheExpiry();
      return updated;
    },
    mutateDataPieceWithPython: async ({
      basePayload,
      password,
      mode,
      schema_revision,
    }) => {
      const mutatedPayload = mutateEncryptedPayload(
        basePayload,
        password,
        mode,
      );
      const current = pieces.get("DATA");
      const updated: StoredBackupPiece = {
        id: randomUUID(),
        protocol: 1,
        date: nextFutureIsoDate(current?.date),
        type: "DATA",
        size: mutatedPayload.length,
        ...(schema_revision !== undefined ? { schema_revision } : {}),
        payload: mutatedPayload,
      };
      pieces.set("DATA", updated);
      await waitForBackendInfoCacheExpiry();
      return updated;
    },
    createBackdatedBackupPiece: ({ piece, password, date }) => {
      const payload = mutateEncryptedPayload(
        piece.payload,
        password,
        "backdate_last_update",
        date,
      );
      return {
        ...piece,
        id: randomUUID(),
        date,
        size: payload.length,
        payload,
      };
    },
    clear: async () => {
      pieces.clear();
      stagedUploads.clear();
      await waitForBackendInfoCacheExpiry();
    },
    close: () => new Promise<void>((resolve) => server.close(() => resolve())),
  };
}

function encodeBase64Url(obj: Record<string, unknown>): string {
  return Buffer.from(JSON.stringify(obj)).toString("base64url");
}

export function createMockCloudJwt(email = "test@example.com"): string {
  const header = encodeBase64Url({ kid: email, alg: "HS256", typ: "JWT" });
  const payload = encodeBase64Url({
    sub: "mock-user-id-e2e",
    email,
    user_role: "PLUS",
    permissions: [
      "backup.info",
      "backup.create",
      "backup.import",
      "backup.erase",
      "backup.auto",
    ],
    exp: Math.floor(Date.now() / 1000) + 3600,
  });
  const signature = Buffer.from("e2e-mock-hmac-sha256-signature!!").toString(
    "base64url",
  );
  return `${header}.${payload}.${signature}`;
}

export async function setupSupabaseMockRoutes(
  page: Page,
  email = "test@example.com",
): Promise<void> {
  const accessToken = createMockCloudJwt(email);
  const nowIso = new Date().toISOString();
  const userPayload = {
    id: "mock-user-id-e2e",
    aud: "authenticated",
    role: "authenticated",
    email,
    email_confirmed_at: nowIso,
    app_metadata: { provider: "email", providers: ["email"] },
    user_metadata: {},
    identities: [
      {
        id: "mock-identity-id",
        user_id: "mock-user-id-e2e",
        identity_data: { email },
        provider: "email",
        created_at: nowIso,
        updated_at: nowIso,
      },
    ],
    created_at: nowIso,
    updated_at: nowIso,
  };
  const sessionPayload = {
    access_token: accessToken,
    token_type: "bearer",
    expires_in: 3600,
    expires_at: Math.floor(Date.now() / 1000) + 3600,
    refresh_token: "mock-refresh-token-e2e",
    user: userPayload,
  };

  await page.route("**/auth/v1/token**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(sessionPayload),
    }),
  );
  await page.route("**/auth/v1/user**", (route) =>
    route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify(userPayload),
    }),
  );
  await page.route("**/auth/v1/logout**", (route) =>
    route.fulfill({
      status: 204,
      body: "",
    }),
  );
}
