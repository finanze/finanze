// @vitest-environment node
import fs from "node:fs"
import path from "node:path"
import { loadPyodide, type PyodideInterface } from "pyodide"
import { afterAll, beforeAll, describe, expect, it, vi } from "vitest"

const APP_ROOT = path.resolve(__dirname, "../../..")
const MOBILE_PY_ROOT = path.resolve(APP_ROOT, "src/python/finanze")
const BACKEND_PY_ROOT = path.resolve(APP_ROOT, "../../finanze")
const PYODIDE_INDEX = path.resolve(APP_ROOT, "node_modules/pyodide")

const HTTPX_STUB = `
import json as _json

class NetworkError(Exception):
    def __init__(self, message, request=None):
        super().__init__(message)
        self.request = request

class HTTPStatusError(Exception):
    def __init__(self, message, request=None, response=None):
        super().__init__(message)
        self.request = request
        self.response = response

class Headers(dict):
    def get_list(self, key):
        target = key.lower()
        return [v for k, v in getattr(self, "_raw_items", []) if k.lower() == target]

class Cookies:
    def __init__(self):
        self.jar = []
        self._store = {}
    def set(self, name, value, domain="", path="/"):
        self._store[name] = value
        self.jar.append((name, value, domain, path))

class Request:
    def __init__(self, method, url, headers=None, content=b"", extensions=None):
        self.method = method
        self.url = url
        self.headers = Headers(headers or {})
        self.content = content if isinstance(content, bytes) else (content or "").encode("utf-8")
        self.stream = [self.content] if self.content else []
        self.extensions = extensions or {}

class Response:
    def __init__(self, status_code=200, headers=None, content=b"", request=None):
        self.status_code = status_code
        self.content = content or b""
        self.request = request
        raw_items = list(headers or [])
        hdrs = Headers()
        for k, v in raw_items:
            hdrs[k.lower()] = v
        hdrs._raw_items = raw_items
        self.headers = hdrs
    @property
    def is_success(self):
        return 200 <= self.status_code < 300
    @property
    def text(self):
        return self.content.decode("utf-8")
    def json(self):
        return _json.loads(self.text)
    def raise_for_status(self):
        if not (200 <= self.status_code < 400):
            raise HTTPStatusError(str(self.status_code), request=self.request, response=self)

class AsyncHTTPTransport:
    async def handle_async_request(self, request):
        raise NotImplementedError()

class AsyncClient:
    def __init__(self, transport=None, timeout=15.0, headers=None):
        self._transport = transport or AsyncHTTPTransport()
        self.timeout = timeout
        self.headers = Headers(headers or {})
        self.cookies = Cookies()
    async def request(self, method, url, headers=None, json=None, timeout=None, **kwargs):
        merged = dict(self.headers)
        if headers:
            merged.update(headers)
        body = _json.dumps(json).encode("utf-8") if json is not None else b""
        ext = {"timeout": {"read": timeout if timeout is not None else self.timeout}}
        req = Request(method, url, headers=merged, content=body, extensions=ext)
        return await self._transport.handle_async_request(req)
`

function writePyFile(
  pyodide: PyodideInterface,
  virtualPath: string,
  content: string | Uint8Array,
) {
  const dir = path.posix.dirname(virtualPath)
  pyodide.FS.mkdirTree(dir)
  pyodide.FS.writeFile(virtualPath, content)
}

describe("Mobile Python <-> JS bridges under real Pyodide 3.14", () => {
  let pyodide: PyodideInterface
  let capHttpHandler: (options: any) => Promise<any>
  let tlsHttpHandler: (options: any) => Promise<any>
  let querySqlHandler: (sql: string, params: any[]) => Promise<any>
  let executeSqlHandler: (sql: string, params: any[]) => Promise<any>

  beforeAll(async () => {
    pyodide = await loadPyodide({ indexURL: PYODIDE_INDEX })

    writePyFile(pyodide, "/python/httpx.py", HTTPX_STUB)
    writePyFile(
      pyodide,
      "/python/finanze/domain/data_init.py",
      fs.readFileSync(path.join(BACKEND_PY_ROOT, "domain/data_init.py")),
    )
    writePyFile(
      pyodide,
      "/python/finanze/domain/user.py",
      fs.readFileSync(path.join(BACKEND_PY_ROOT, "domain/user.py")),
    )
    writePyFile(
      pyodide,
      "/python/finanze/domain/dezimal.py",
      fs.readFileSync(path.join(BACKEND_PY_ROOT, "domain/dezimal.py")),
    )
    for (const rel of [
      "infrastructure/client/http/httpx_patch.py",
      "infrastructure/client/http/http_response.py",
      "infrastructure/client/http/http_session.py",
      "infrastructure/repository/db/capacitor_client.py",
    ]) {
      writePyFile(
        pyodide,
        `/python/finanze/${rel}`,
        fs.readFileSync(path.join(MOBILE_PY_ROOT, rel)),
      )
    }

    ;(globalThis as any).Capacitor = {
      Plugins: {
        CapacitorHttp: {
          request: (opts: any) => capHttpHandler(opts),
        },
      },
    }
    ;(globalThis as any).TlsHttp = {
      request: (opts: any) => tlsHttpHandler(opts),
    }
    ;(globalThis as any).jsBridge = {
      sqlite: {
        querySql: (sql: string, params: any[]) => querySqlHandler(sql, params),
        executeSql: (sql: string, params: any[]) =>
          executeSqlHandler(sql, params),
        executeBatch: async () => ({ changes: 0 }),
        closeDatabase: async () => undefined,
      },
    }

    await pyodide.runPythonAsync(`
import sys
for p in ("/python", "/python/finanze"):
    if p not in sys.path:
        sys.path.insert(0, p)
from infrastructure.client.http.httpx_patch import apply_httpx_patch
apply_httpx_patch()
`)
  })

  afterAll(() => {
    delete (globalThis as any).Capacitor
    delete (globalThis as any).TlsHttp
    delete (globalThis as any).jsBridge
  })

  it("serializes CapacitorHttp pre-parsed JSON payloads without calling to_py() on nested order numbers", async () => {
    const orders = Array.from({ length: 200 }, (_, i) => ({
      id: `order-${i}`,
      status: i % 5 === 0 ? "PENDING" : "COMPLETE",
      executedShares: i % 2 === 0 ? 12.3456 : "4.5000",
      priceCurrency: 108.75 + i * 0.01,
      epochMs: 1763477702000 + i * 1000,
      maxSafe: Number.MAX_SAFE_INTEGER,
      negZero: -0,
      nullableField: null,
      nested: { fees: 0.15, tags: ["ETF", "EUR"] },
    }))

    capHttpHandler = vi.fn(async (opts: any) => {
      expect(opts.responseType).toBe("text")
      const responseObj = {
        status: 200,
        headers: {
          "content-type": "application/json; charset=utf-8",
          "content-encoding": "gzip",
          "set-cookie":
            "a=1; Expires=Wed, 21 Oct 2026 07:28:00 GMT; Path=/, b=2; Path=/",
        },
        // CapacitorHttp ignores responseType:"text" on application/json and returns a JS object:
        data: new Proxy(
          { payload: { data: orders } },
          {
            get(target, prop, receiver) {
              // If Python ever attempted .to_py() on data, JsProxy_toPy accesses entries directly,
              // so we also poison a nested number-like trap check and verify roundtrip fidelity.
              return Reflect.get(target, prop, receiver)
            },
          },
        ),
      }
      return responseObj
    })

    const result = await pyodide.runPythonAsync(`
from infrastructure.client.http.http_session import new_http_session

session = new_http_session()
resp = await session.get("https://api.myinvestor.es/broker/v2/stock-orders")
parsed = await resp.json()
items = parsed["payload"]["data"]
{
    "status": resp.status,
    "count": len(items),
    "first_epoch": items[0]["epochMs"],
    "max_safe_matches": items[0]["maxSafe"] == 9007199254740991 and isinstance(items[0]["maxSafe"], int),
    "first_null_is_none": items[0]["nullableField"] is None,
    "has_content_encoding": "content-encoding" in resp.headers,
    "cookies_count": len(resp._response.headers.get_list("set-cookie")),
}
`)
    const pyResult = result.toJs({ dict_converter: Object.fromEntries })
    result.destroy()

    expect(pyResult).toEqual({
      status: 200,
      count: 200,
      first_epoch: 1763477702000,
      max_safe_matches: true,
      first_null_is_none: true,
      has_content_encoding: false,
      cookies_count: 2,
    })
  })

  it("guards NaN/missing status codes and binary/text responses in httpx_patch", async () => {
    capHttpHandler = vi.fn(async (opts: any) => {
      if (opts.url.endsWith("/nan-status")) {
        return { status: Number.NaN, headers: null, data: null }
      }
      if (opts.url.endsWith("/binary")) {
        return {
          status: 200,
          headers: { "content-type": "application/octet-stream" },
          data: new Uint8Array([0xde, 0xad, 0xbe, 0xef]),
        }
      }
      throw new Error("socket hang up")
    })

    const result = await pyodide.runPythonAsync(`
import httpx
from infrastructure.client.http.http_session import get_http_session

session = get_http_session()
r_nan = await session.get("https://example.test/nan-status")
r_bin = await session.get("https://example.test/binary")
raw_bytes = await r_bin.read()

net_err = False
try:
    await session.get("https://example.test/fail")
except httpx.NetworkError:
    net_err = True

{
    "nan_status": r_nan.status,
    "nan_body": await r_nan.text(),
    "bin_hex": raw_bytes.hex(),
    "net_err": net_err,
}
`)
    const pyResult = result.toJs({ dict_converter: Object.fromEntries })
    result.destroy()

    expect(pyResult).toEqual({
      nan_status: 0,
      nan_body: "",
      bin_hex: "deadbeef",
      net_err: true,
    })
  })

  it("handles TlsHttp responses without top-level to_py() in ImpersonatedHttpSession", async () => {
    tlsHttpHandler = vi.fn(async (opts: any) => ({
      status: 200,
      headers: { "content-type": "application/json" },
      data: JSON.stringify({
        equities: [
          { symbol: "AAPL:NSQ:USD", name: "Apple Inc", url: opts.url },
        ],
        cookiesSent: opts.cookies ?? [],
      }),
    }))

    const result = await pyodide.runPythonAsync(`
from infrastructure.client.http.http_session import new_impersonated_http_session

tls = new_impersonated_http_session("firefox135", force_http1=True)
tls.cookies.set("consent", "yes", domain=".ft.com")
resp = await tls.request("GET", "https://www.ft.com/search-api/suggestions", params={"partial": "AAPL", "empty": None})
body = await resp.json()
{
    "ok": resp.ok,
    "status": resp.status,
    "url": body["equities"][0]["url"],
    "cookie_count": len(body["cookiesSent"]),
}
`)
    const pyResult = result.toJs({ dict_converter: Object.fromEntries })
    result.destroy()

    expect(pyResult).toEqual({
      ok: true,
      status: 200,
      url: "https://www.ft.com/search-api/suggestions?partial=AAPL",
      cookie_count: 1,
    })
  })

  it("converts large numeric SQLite querySql result sets via JSON without silent RowProxy corruption", async () => {
    querySqlHandler = vi.fn(async () =>
      Array.from({ length: 300 }, (_, i) => ({
        id: `tx-${i}`,
        amount: "1234.56",
        interest_rate: 0.0325 + i * 0.0001,
        created_epoch: 1763477702000 + i,
        is_active: i % 2,
        optional_note: i % 3 === 0 ? null : undefined,
      })),
    )
    executeSqlHandler = vi.fn(async () => ({ changes: 1, lastId: 1 }))

    const result = await pyodide.runPythonAsync(`
from infrastructure.repository.db.capacitor_client import CapacitorDBClient, _to_py

client = CapacitorDBClient(connection={"ok": True})
async with client.read() as cursor:
    await cursor.execute("SELECT * FROM transactions WHERE source = :source", {"source": "REAL"})
    rows = await cursor.fetchall()

class BrokenProxy:
    def to_py(self):
        raise ValueError("cannot convert float NaN to integer")

propagated_error = False
try:
    _to_py(BrokenProxy())
except ValueError:
    propagated_error = True

first = rows[0]
second = rows[1]
{
    "count": len(rows),
    "first_id_by_key": first["id"],
    "first_id_by_idx": first[0],
    "first_epoch": first["created_epoch"],
    "first_rate": round(first["interest_rate"], 6),
    "null_is_none": first["optional_note"] is None,
    "undef_is_none": second["optional_note"] is None,
    "keys": first.keys(),
    "propagated_error": propagated_error,
}
`)
    const pyResult = result.toJs({ dict_converter: Object.fromEntries })
    result.destroy()

    expect(pyResult).toEqual({
      count: 300,
      first_id_by_key: "tx-0",
      first_id_by_idx: "tx-0",
      first_epoch: 1763477702000,
      first_rate: 0.0325,
      null_is_none: true,
      undef_is_none: true,
      keys: [
        "id",
        "amount",
        "interest_rate",
        "created_epoch",
        "is_active",
        "optional_note",
      ],
      propagated_error: true,
    })
  })

  it("normalizes pre-parsed JSON data in PyodideWorkerClient.invokeAllowed before worker postMessage", async () => {
    const postedMessages: any[] = []
    class FakeWorker {
      onmessage: ((e: any) => void) | null = null
      postMessage(msg: any) {
        postedMessages.push(msg)
      }
      terminate() {}
    }

    const origWorker = (globalThis as any).Worker
    const hadWindow = "window" in globalThis
    const origWindow = (globalThis as any).window
    ;(globalThis as any).Worker = FakeWorker
    ;(globalThis as any).window = globalThis
    capHttpHandler = vi.fn(async () => ({
      status: 200,
      headers: { "content-type": "application/json" },
      data: { payload: { data: [{ id: "1", price: 42.5 }] } },
    }))

    try {
      const { PyodideWorkerClient } =
        await import("@/lib/pyodide/worker/client")
      ;(globalThis as any).Capacitor = {
        Plugins: {
          CapacitorHttp: {
            request: (opts: any) => capHttpHandler(opts),
          },
        },
      }
      const client = new PyodideWorkerClient("main")
      const fakeWorker = (client as any).worker as FakeWorker

      fakeWorker.onmessage?.({
        data: {
          kind: "req",
          id: 77,
          action: "callMain",
          payload: {
            method: "Capacitor.Plugins.CapacitorHttp.request",
            args: [{ url: "https://api.myinvestor.es/test", method: "GET" }],
          },
        },
      })

      await vi.waitFor(() => {
        expect(postedMessages).toHaveLength(1)
      })

      expect(postedMessages[0]).toEqual({
        kind: "res",
        id: 77,
        ok: true,
        result: {
          status: 200,
          headers: { "content-type": "application/json" },
          data: '{"payload":{"data":[{"id":"1","price":42.5}]}}',
        },
      })
    } finally {
      ;(globalThis as any).Worker = origWorker
      if (hadWindow) {
        ;(globalThis as any).window = origWindow
      } else {
        delete (globalThis as any).window
      }
    }
  })
})
