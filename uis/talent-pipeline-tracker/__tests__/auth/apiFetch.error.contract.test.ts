/**
 * Simulated fetch — shared auth client error sanitization contract (I03b).
 */

import { apiFetch } from "@/lib/auth/api";
import { AUTH_TOKEN_STORAGE_KEY } from "@/lib/auth/constants";
import { ApiError } from "@/lib/auth/types";
import {
  GENERIC_ERROR_MESSAGE,
  NETWORK_ERROR_MESSAGE,
  resolveUserFacingApiText,
  VALIDATION_FORM_SUMMARY_MESSAGE,
} from "@/lib/auth/userFacingError";
import { track } from "@/src/services/telemetry";

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
      location: { pathname: "/account/profile", assign: assignMock },
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

const mockFetchJson = (
  status: number,
  body: unknown,
  contentType = "application/json",
): void => {
  global.fetch = jest.fn().mockResolvedValue({
    status,
    ok: status >= 200 && status < 300,
    json: async () => body,
    headers: new Headers({ "content-type": contentType }),
  } as Response);
};

const seedAuthedSession = (): void => {
  memoryStore[AUTH_TOKEN_STORAGE_KEY] = "jwt-token";
};

const CLIENT_400_FALLBACK =
  "The request could not be completed. Check your information and try again.";
const CLIENT_403_FALLBACK = "You do not have permission to do that.";

beforeEach(() => {
  jest.clearAllMocks();
  for (const key of Object.keys(memoryStore)) {
    delete memoryStore[key];
  }
  assignMock.mockReset();
  installBrowserGlobals();
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
});

describe("resolveUserFacingApiText — source-backed manager copy", () => {
  it("allows enum list messages from incident_service", () => {
    expect(
      resolveUserFacingApiText(
        400,
        "Category must be one of: clinical_equipment, it_system, billing_error, compliance_breach, patient_experience, staff_issue, facility_issue, referral_issue, other.",
      ),
    ).toContain("Category must be one of:");
  });

  it("allows constrained CSV missing-column suffix", () => {
    expect(
      resolveUserFacingApiText(
        400,
        "Incorrect CSV format: missing required columns: incident_id, date",
      ),
    ).toBe("Incorrect CSV format: missing required columns: incident_id, date");
  });

  it("allows status transition copy with sorted targets", () => {
    expect(
      resolveUserFacingApiText(
        400,
        "An open incident can only move to: discarded, in_progress.",
      ),
    ).toBe("An open incident can only move to: discarded, in_progress.");
  });

  it("falls back for insufficient stock (variable catalog name)", () => {
    expect(
      resolveUserFacingApiText(
        400,
        "Insufficient stock for supply 'Gloves'. Available: 2, requested: 5.",
      ),
    ).toBe(CLIENT_400_FALLBACK);
  });

  it("falls back for embedded markup in plausible required copy", () => {
    expect(
      resolveUserFacingApiText(400, "<img src=x onerror=alert(1)> is required."),
    ).toBe(CLIENT_400_FALLBACK);
  });

  it("falls back for non-numeric supplier detail", () => {
    expect(
      resolveUserFacingApiText(404, "Supplier ../../../../etc/passwd not found"),
    ).toBe("The requested information could not be found.");
  });

  it("allows numeric supplier id shape", () => {
    expect(resolveUserFacingApiText(404, "Supplier 42 not found")).toBe(
      "Supplier 42 not found",
    );
  });
});

describe("apiFetch error contract (simulated)", () => {
  it("400 manager field/message preserves association for approved copy", async () => {
    seedAuthedSession();
    mockFetchJson(400, {
      field: "title",
      message: "Title is required.",
    });
    await expect(
      apiFetch("/api/incidents", {
        auth: true,
        method: "POST",
        body: "{}",
      }),
    ).rejects.toMatchObject({
      status: 400,
      message: "Title is required.",
      fieldErrors: { title: "Title is required." },
    });
  });

  it("400 manager field/message sanitizes unsafe text but keeps field key", async () => {
    seedAuthedSession();
    const leaky = "Traceback (most recent call last): File /secret/path.py";
    mockFetchJson(400, { field: "title", message: leaky });
    await expect(apiFetch("/probe", { auth: true })).rejects.toMatchObject({
      status: 400,
      message: CLIENT_400_FALLBACK,
      fieldErrors: { title: CLIENT_400_FALLBACK },
    });
  });

  it("400 detail shows whitelisted analyzer copy", async () => {
    seedAuthedSession();
    mockFetchJson(400, { detail: "The CSV file is empty." });
    await expect(apiFetch("/api/incidents/analyze", { auth: true })).rejects
      .toMatchObject({
        status: 400,
        message: "The CSV file is empty.",
      });
  });

  it("404 detail shows whitelisted application copy", async () => {
    seedAuthedSession();
    mockFetchJson(404, {
      detail: "No analysis available. Upload a CSV to /api/incidents/analyze first.",
    });
    await expect(apiFetch("/api/incidents/results", { auth: true })).rejects
      .toMatchObject({
        status: 404,
        message:
          "No analysis available. Upload a CSV to /api/incidents/analyze first.",
      });
  });

  it("400 detail sanitizes technical-looking text", async () => {
    seedAuthedSession();
    const leaky = "Traceback (most recent call last): File /secret/path.py";
    mockFetchJson(400, { detail: leaky });
    await expect(apiFetch("/probe", { auth: true })).rejects.toMatchObject({
      status: 400,
      message: CLIENT_400_FALLBACK,
    });
  });

  it("404 detail sanitizes unlisted arbitrary strings", async () => {
    seedAuthedSession();
    mockFetchJson(404, { detail: "Internal lookup failed in module xyz" });
    await expect(apiFetch("/probe", { auth: true })).rejects.toMatchObject({
      status: 404,
      message: "The requested information could not be found.",
    });
  });

  it("500 detail is sanitized", async () => {
    seedAuthedSession();
    mockFetchJson(500, {
      detail: "Traceback (most recent call last): secret",
    });
    await expect(apiFetch("/probe", { auth: true })).rejects.toMatchObject({
      status: 500,
      message: GENERIC_ERROR_MESSAGE,
    });
  });

  it("500 standalone message allows only whitelisted application copy", async () => {
    seedAuthedSession();
    mockFetchJson(500, {
      message: "An unexpected error occurred. Please try again.",
    });
    await expect(apiFetch("/probe", { auth: true })).rejects.toMatchObject({
      status: 500,
      message: "An unexpected error occurred. Please try again.",
    });
  });

  it("500 standalone message sanitizes unsafe text", async () => {
    seedAuthedSession();
    mockFetchJson(500, {
      message: "Traceback (most recent call last): File /app/main.py",
    });
    await expect(apiFetch("/probe", { auth: true })).rejects.toMatchObject({
      status: 500,
      message: GENERIC_ERROR_MESSAGE,
    });
  });

  it("422 array maps fields with safe summary and field association", async () => {
    mockFetchJson(422, {
      detail: [
        {
          type: "string_too_short",
          loc: ["body", "password"],
          msg: "String should have at least 8 characters",
          input: "short",
          ctx: { min_length: 8 },
        },
        {
          type: "value_error",
          loc: ["body", "email"],
          msg: "value is not a valid email address",
          input: "not-an-email",
        },
      ],
    });
    try {
      await apiFetch("/users", { method: "POST", body: "{}" });
    } catch (error) {
      expect(error).toBeInstanceOf(ApiError);
      const apiError = error as ApiError;
      expect(apiError.message).toBe(VALIDATION_FORM_SUMMARY_MESSAGE);
      expect(apiError.fieldErrors).toEqual({
        password: "Password must be at least 8 characters.",
        email: "Enter a valid email address.",
      });
      expect(JSON.stringify(apiError.fieldErrors)).not.toContain("input");
      expect(JSON.stringify(apiError.fieldErrors)).not.toContain(
        "string_too_short",
      );
      return;
    }
    throw new Error("expected ApiError");
  });

  it("403 RFP machine code uses safe fallback", async () => {
    seedAuthedSession();
    mockFetchJson(403, { detail: "not_department_owner" });
    await expect(
      apiFetch("/rfp/tickets/x/approval/y", { auth: true, method: "POST" }),
    ).rejects.toMatchObject({
      status: 403,
      message: CLIENT_403_FALLBACK,
    });
  });

  it("400 auth reset exception text uses safe fallback", async () => {
    mockFetchJson(400, {
      detail: "Invalid or expired reset token (internal ref abc123)",
    });
    await expect(
      apiFetch("/auth/reset-password", {
        method: "POST",
        body: "{}",
      }),
    ).rejects.toMatchObject({
      status: 400,
      message: CLIENT_400_FALLBACK,
    });
  });

  it("network failure uses NETWORK_ERROR_MESSAGE", async () => {
    global.fetch = jest.fn().mockRejectedValue(new TypeError("fetch failed"));
    await expect(apiFetch("/health")).rejects.toMatchObject({
      status: 0,
      message: NETWORK_ERROR_MESSAGE,
    });
  });

  it("non-JSON error body uses status fallback", async () => {
    global.fetch = jest.fn().mockResolvedValue({
      status: 503,
      ok: false,
      json: async () => {
        throw new SyntaxError("Unexpected token");
      },
    } as Response);
    await expect(apiFetch("/health")).rejects.toMatchObject({
      status: 503,
      message: GENERIC_ERROR_MESSAGE,
    });
  });

  it("401 on authed call clears token, redirects, and emits telemetry", async () => {
    memoryStore[AUTH_TOKEN_STORAGE_KEY] = "jwt-token";
    mockFetchJson(401, { detail: "Could not validate credentials" });
    await expect(
      apiFetch("/auth/me", { auth: true, method: "GET" }),
    ).rejects.toMatchObject({
      status: 401,
      message: "Your session expired. Please sign in again.",
    });
    expect(memoryStore[AUTH_TOKEN_STORAGE_KEY]).toBeUndefined();
    expect(assignMock).toHaveBeenCalledWith("/login");
    expect(track).toHaveBeenCalledWith(
      "session_expired",
      expect.objectContaining({ expiry_source: "auth_me_401" }),
    );
    expect(track).toHaveBeenCalledWith(
      "user_logout_completed",
      expect.objectContaining({ logout_method: "forced_401" }),
    );
  });

  it("successful JSON parse returns payload", async () => {
    mockFetchJson(200, { status: "ok" });
    await expect(apiFetch<{ status: string }>("/health")).resolves.toEqual({
      status: "ok",
    });
  });

  it("204 returns undefined", async () => {
    seedAuthedSession();
    global.fetch = jest.fn().mockResolvedValue({
      status: 204,
      ok: true,
      json: async () => ({}),
    } as Response);
    await expect(
      apiFetch<void>("/resource", { method: "DELETE", auth: true }),
    ).resolves.toBeUndefined();
  });

  it("form login keeps json false (no forced JSON content-type on empty body edge)", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      status: 200,
      ok: true,
      json: async () => ({ access_token: "tok" }),
    } as Response);
    global.fetch = fetchMock;
    await apiFetch("/auth/login", {
      method: "POST",
      json: false,
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: "username=a%40b.com&password=secret",
    });
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    const requestHeaders = init.headers as Headers;
    expect(requestHeaders.get("Content-Type")).toBe(
      "application/x-www-form-urlencoded",
    );
  });
});
