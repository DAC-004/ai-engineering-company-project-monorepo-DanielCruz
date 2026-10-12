/**
 * incidentAnalyzer uses authorizedFetch (not apiFetch JSON parsing).
 * Covers JWT attachment, 401 session clear, and non-OK export without blob save.
 */

import { analyzeIncidentCsv, downloadIncidentResultsCsv } from "@/lib/incidentAnalyzer";

const mockClear = jest.fn();
const mockGetToken = jest.fn();

jest.mock("@/lib/auth/api", () => ({
  clearSessionAndRedirectToLogin: (...args: unknown[]) => mockClear(...args),
}));

jest.mock("@/lib/auth/token", () => ({
  getAccessToken: () => mockGetToken(),
}));

describe("incidentAnalyzer authorized transport", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    mockClear.mockClear();
    mockGetToken.mockReset();
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
  });

  afterEach(() => {
    global.fetch = originalFetch;
  });

  it("redirects when token is missing before upload", async () => {
    mockGetToken.mockReturnValue(null);
    await expect(analyzeIncidentCsv(new File(["a"], "t.csv"))).rejects.toMatchObject({
      status: 401,
    });
    expect(mockClear).toHaveBeenCalledTimes(1);
    expect(global.fetch).toBe(originalFetch);
  });

  it("sends Authorization only to the HealthCore API base for upload", async () => {
    mockGetToken.mockReturnValue("test-jwt");
    global.fetch = jest.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({
        source_name: "t.csv",
        total_records: 0,
        valid_count: 0,
        invalid_count: 0,
        invalid_by_rule: {},
        category_counts: {},
        status_counts: {},
        country_counts: {},
        satisfaction: {
          closed_cases: 0,
          scored_cases: 0,
          average: null,
          score_counts: {},
        },
      }),
    }) as typeof fetch;

    await analyzeIncidentCsv(new File(["h"], "t.csv", { type: "text/csv" }));

    expect(global.fetch).toHaveBeenCalledTimes(1);
    const [url, init] = (global.fetch as jest.Mock).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("http://127.0.0.1:8000/api/incidents/analyze");
    expect((init.headers as Headers).get("Authorization")).toBe("Bearer test-jwt");
    expect(init.body).toBeInstanceOf(FormData);
  });

  it("clears session on 401 export and does not return blob", async () => {
    mockGetToken.mockReturnValue("expired-jwt");
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ detail: "Could not validate credentials" }),
    }) as typeof fetch;

    await expect(downloadIncidentResultsCsv()).rejects.toMatchObject({ status: 401 });
    expect(mockClear).toHaveBeenCalledTimes(1);
  });

  it("throws ApiError on failed export without treating error JSON as CSV", async () => {
    mockGetToken.mockReturnValue("test-jwt");
    global.fetch = jest.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ message: "An unexpected error occurred. Please try again." }),
    }) as typeof fetch;

    await expect(downloadIncidentResultsCsv()).rejects.toMatchObject({ status: 500 });
    expect(global.fetch).toHaveBeenCalledTimes(1);
  });
});
