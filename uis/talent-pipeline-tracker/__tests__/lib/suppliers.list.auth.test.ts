/**
 * listSuppliers must attach the existing session bearer through apiFetch({ auth: true }).
 * Covers authenticated list query params plus the established missing/invalid-token paths.
 */

import { listSuppliers } from "@/lib/suppliers";
import { AUTH_TOKEN_STORAGE_KEY } from "@/lib/auth/constants";

jest.mock("@/src/services/telemetry", () => ({
  track: jest.fn(),
  bindTelemetryRequestId: jest.fn(),
}));

jest.mock("@/lib/telemetry/identity", () => ({
  isJwtExpired: jest.fn(() => false),
}));

jest.mock("@/lib/telemetry/mapping", () => ({
  toApiRouteTemplate: (path: string) => path,
  toRoutePath: (path: string) => path,
}));

const memoryStore: Record<string, string> = {};
const assignMock = jest.fn();

const installBrowserGlobals = (): void => {
  Object.defineProperty(globalThis, "window", {
    value: {
      localStorage: {
        getItem: (key: string) =>
          Object.prototype.hasOwnProperty.call(memoryStore, key)
            ? memoryStore[key]
            : null,
        setItem: (key: string, value: string) => {
          memoryStore[key] = value;
        },
        removeItem: (key: string) => {
          delete memoryStore[key];
        },
      },
      location: { pathname: "/backoffice/suppliers", assign: assignMock },
      crypto: { randomUUID: () => "00000000-0000-4000-8000-000000000001" },
    },
    writable: true,
    configurable: true,
  });
  Object.defineProperty(globalThis, "performance", {
    value: { now: () => 0 },
    writable: true,
    configurable: true,
  });
};

beforeEach(() => {
  jest.clearAllMocks();
  for (const key of Object.keys(memoryStore)) {
    delete memoryStore[key];
  }
  assignMock.mockReset();
  installBrowserGlobals();
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
});

describe("listSuppliers authentication", () => {
  it("sends the session bearer and preserves list filters", async () => {
    memoryStore[AUTH_TOKEN_STORAGE_KEY] = "jwt-token";
    const payload = [
      {
        id: 1,
        name: "Fixture",
        country: "USA",
        categories: ["medical_supplies"],
        monthly_rate: 125,
        currency: "USD",
        updated_at: "2026-11-01T15:30:36.240631Z",
        status: "active",
        compliance_agreement: null,
        contract_renewal_date: null,
        contact_email: null,
        notes: null,
      },
    ];
    const fetchMock = jest.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => payload,
      headers: new Headers({ "content-type": "application/json" }),
    } as Response);
    global.fetch = fetchMock;

    await expect(
      listSuppliers({ country: "USA", category: "medical_supplies" }),
    ).resolves.toEqual(payload);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toBe(
      "http://127.0.0.1:8000/suppliers?country=USA&category=medical_supplies",
    );
    expect((init.headers as Headers).get("Authorization")).toBe(
      "Bearer jwt-token",
    );
  });

  it("uses the established missing-token 401 path and does not fetch", async () => {
    const fetchMock = jest.fn();
    global.fetch = fetchMock;

    await expect(listSuppliers()).rejects.toMatchObject({
      status: 401,
      message: "Your session expired. Please sign in again.",
    });
    expect(fetchMock).not.toHaveBeenCalled();
    expect(assignMock).toHaveBeenCalledWith("/login");
  });

  it("uses the established invalid-token 401 path", async () => {
    memoryStore[AUTH_TOKEN_STORAGE_KEY] = "jwt-token";
    global.fetch = jest.fn().mockResolvedValue({
      status: 401,
      ok: false,
      json: async () => ({ detail: "Could not validate credentials" }),
      headers: new Headers({ "content-type": "application/json" }),
    } as Response);

    await expect(listSuppliers()).rejects.toMatchObject({
      status: 401,
      message: "Your session expired. Please sign in again.",
    });
    expect(memoryStore[AUTH_TOKEN_STORAGE_KEY]).toBeUndefined();
    expect(assignMock).toHaveBeenCalledWith("/login");
  });
});
