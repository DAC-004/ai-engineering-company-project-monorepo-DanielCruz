/**
 * incidentAnalyzer uses authorizedFetch (not apiFetch JSON parsing).
 * Covers JWT attachment, 401 session clear, 202 enqueue + task poll, and export.
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

const sampleResult = {
  source_name: "t.csv",
  total_records: 1,
  valid_count: 1,
  invalid_count: 0,
  invalid_by_rule: {},
  category_counts: { CLINICAL: 1 },
  status_counts: { CLOSED: 1 },
  country_counts: { US: 1 },
  satisfaction: {
    closed_cases: 1,
    scored_cases: 1,
    average: 5,
    score_counts: { "5": 1 },
  },
};

describe("incidentAnalyzer authorized transport", () => {
  const originalFetch = global.fetch;

  beforeEach(() => {
    mockClear.mockClear();
    mockGetToken.mockReset();
    process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000";
    jest.useFakeTimers();
  });

  afterEach(() => {
    global.fetch = originalFetch;
    jest.useRealTimers();
  });

  it("redirects when token is missing before upload", async () => {
    mockGetToken.mockReturnValue(null);
    await expect(analyzeIncidentCsv(new File(["a"], "t.csv"))).rejects.toMatchObject({
      status: 401,
    });
    expect(mockClear).toHaveBeenCalledTimes(1);
    expect(global.fetch).toBe(originalFetch);
  });

  it("sends Authorization for 202 enqueue then polls GET /tasks/{task_id}", async () => {
    mockGetToken.mockReturnValue("test-jwt");
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({ task_id: "task-abc" }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          task_id: "task-abc",
          status: "pending",
          result: null,
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          task_id: "task-abc",
          status: "success",
          result: sampleResult,
        }),
      }) as typeof fetch;

    const analyzePromise = analyzeIncidentCsv(new File(["h"], "t.csv", { type: "text/csv" }));
    await jest.advanceTimersByTimeAsync(250);
    const payload = await analyzePromise;

    expect(payload.total_records).toBe(1);
    expect(global.fetch).toHaveBeenCalledTimes(3);
    const [uploadUrl, uploadInit] = (global.fetch as jest.Mock).mock.calls[0] as [
      string,
      RequestInit,
    ];
    expect(uploadUrl).toBe("http://127.0.0.1:8000/api/incidents/analyze");
    expect((uploadInit.headers as Headers).get("Authorization")).toBe("Bearer test-jwt");
    expect(uploadInit.body).toBeInstanceOf(FormData);
    const [pollUrl] = (global.fetch as jest.Mock).mock.calls[2] as [string, RequestInit];
    expect(pollUrl).toBe("http://127.0.0.1:8000/tasks/task-abc");
  });

  it("clears session on 401 during task poll", async () => {
    mockGetToken.mockReturnValue("expired-jwt");
    global.fetch = jest
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 202,
        json: async () => ({ task_id: "task-xyz" }),
      })
      .mockResolvedValueOnce({
        ok: false,
        status: 401,
        json: async () => ({ detail: "Could not validate credentials" }),
      }) as typeof fetch;

    await expect(
      analyzeIncidentCsv(new File(["h"], "t.csv", { type: "text/csv" })),
    ).rejects.toMatchObject({ status: 401 });
    expect(mockClear).toHaveBeenCalledTimes(1);
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
