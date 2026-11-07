/**
 * Client helpers attach the session bearer. This is not a render test and does
 * not prove live API integration.
 */

import {
  getMyOnboarding,
  getOnboarding,
  listOnboardings,
  submitCheck,
  submitDecision,
  waitForOnboardingJob,
} from "@/lib/onboarding";
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
      crypto: { randomUUID: () => "11111111-1111-4111-8111-111111111111" },
      location: { pathname: "/onboarding/me", assign: jest.fn() },
    },
    configurable: true,
  });
  if (typeof globalThis.performance === "undefined" || typeof globalThis.performance.now !== "function") {
    Object.defineProperty(globalThis, "performance", {
      value: { now: () => Date.now() },
      configurable: true,
    });
  }
  process.env.NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8020";
};

describe("onboarding client auth", () => {
  beforeEach(() => {
    for (const key of Object.keys(memoryStore)) {
      delete memoryStore[key];
    }
    installBrowserGlobals();
    memoryStore[AUTH_TOKEN_STORAGE_KEY] = "test-token";
  });

  it("sends the bearer on list and me", async () => {
    const fetchMock = jest.fn().mockResolvedValue({
      ok: true,
      json: async () => [],
    });
    global.fetch = fetchMock as unknown as typeof fetch;
    await listOnboardings();
    await getMyOnboarding();
    await getOnboarding("onb-austin");
    expect(fetchMock).toHaveBeenCalledTimes(3);
    for (const call of fetchMock.mock.calls) {
      const init = call[1] as RequestInit;
      const headers = init.headers as Headers;
      expect(headers.get("Authorization")).toBe("Bearer test-token");
      expect(String(call[0])).toContain("/onboarding");
    }
  });
});

describe("onboarding delayed job wait", () => {
  beforeEach(() => {
    for (const key of Object.keys(memoryStore)) {
      delete memoryStore[key];
    }
    installBrowserGlobals();
    memoryStore[AUTH_TOKEN_STORAGE_KEY] = "test-token";
  });

  const jsonResponse = (status: number, body: unknown) => ({
    ok: status >= 200 && status < 300,
    status,
    json: async () => body,
  });

  it("waits through delayed PENDING jobs and only resolves on SUCCESS", async () => {
    let jobCalls = 0;
    global.fetch = jest.fn(async (url: string | URL, init?: RequestInit) => {
      const path = String(url);
      if (path.endsWith("/onboarding/onb-austin/check") && init?.method === "POST") {
        return jsonResponse(202, {
          accepted: true,
          task_id: "job-delayed",
          onboarding_id: "onb-austin",
          actor_type: "automated_process",
        });
      }
      if (path.includes("/onboarding/jobs/job-delayed")) {
        jobCalls += 1;
        if (jobCalls < 3) {
          return jsonResponse(200, {
            task_id: "job-delayed",
            state: "PENDING",
            ready: false,
          });
        }
        return jsonResponse(200, {
          task_id: "job-delayed",
          state: "SUCCESS",
          ready: true,
        });
      }
      throw new Error(`unexpected fetch ${path}`);
    }) as unknown as typeof fetch;

    const accepted = await submitCheck("onb-austin", {
      answers: [0, 0, 0, 0, 0],
      decision_nonce: "nonce-1",
    });
    expect(accepted.task_id).toBe("job-delayed");
    expect(jobCalls).toBe(0);

    const job = await waitForOnboardingJob(accepted.task_id, {
      intervalMs: 5,
      timeoutMs: 1000,
    });
    expect(job.state).toBe("SUCCESS");
    expect(jobCalls).toBeGreaterThanOrEqual(3);
  });

  it("does not treat ready=true FAILURE as success", async () => {
    global.fetch = jest.fn(async () =>
      jsonResponse(200, {
        task_id: "job-fail",
        state: "FAILURE",
        ready: true,
      }),
    ) as unknown as typeof fetch;

    await expect(
      waitForOnboardingJob("job-fail", { intervalMs: 5, timeoutMs: 200 }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 409,
      message: "Onboarding job ended with FAILURE.",
    });
  });

  it("throws when a delayed job stays non-terminal past the timeout", async () => {
    global.fetch = jest.fn(async () =>
      jsonResponse(200, {
        task_id: "job-hang",
        state: "PENDING",
        ready: false,
      }),
    ) as unknown as typeof fetch;

    await expect(
      waitForOnboardingJob("job-hang", { intervalMs: 5, timeoutMs: 25 }),
    ).rejects.toMatchObject({
      name: "ApiError",
      status: 408,
      message: "Onboarding job timed out.",
    });
  });

  it("throws when the wait is cancelled before SUCCESS", async () => {
    global.fetch = jest.fn(async () =>
      jsonResponse(200, {
        task_id: "job-cancel",
        state: "STARTED",
        ready: false,
      }),
    ) as unknown as typeof fetch;
    const controller = new AbortController();
    const waiting = waitForOnboardingJob("job-cancel", {
      intervalMs: 20,
      timeoutMs: 1000,
      signal: controller.signal,
    });
    controller.abort();
    await expect(waiting).rejects.toMatchObject({
      name: "ApiError",
      status: 499,
      message: "Onboarding job wait was cancelled.",
    });
  });

  it("polls People decisions until SUCCESS instead of returning at 202", async () => {
    let jobCalls = 0;
    global.fetch = jest.fn(async (url: string | URL, init?: RequestInit) => {
      const path = String(url);
      if (path.endsWith("/onboarding/onb-austin/decision") && init?.method === "POST") {
        return jsonResponse(202, {
          accepted: true,
          task_id: "job-people",
          onboarding_id: "onb-austin",
          actor_type: "compliance_officer",
        });
      }
      if (path.includes("/onboarding/jobs/job-people")) {
        jobCalls += 1;
        if (jobCalls === 1) {
          return jsonResponse(200, {
            task_id: "job-people",
            state: "STARTED",
            ready: false,
          });
        }
        return jsonResponse(200, {
          task_id: "job-people",
          state: "SUCCESS",
          ready: true,
        });
      }
      throw new Error(`unexpected fetch ${path}`);
    }) as unknown as typeof fetch;

    const accepted = await submitDecision("onb-austin", {
      decision: "approve",
      comment: "",
      decision_nonce: "nonce-2",
    });
    expect(jobCalls).toBe(0);
    const job = await waitForOnboardingJob(accepted.task_id, {
      intervalMs: 5,
      timeoutMs: 1000,
    });
    expect(job.state).toBe("SUCCESS");
    expect(jobCalls).toBeGreaterThanOrEqual(2);
  });
});
