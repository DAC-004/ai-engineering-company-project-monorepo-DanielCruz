import {
  clearAccessToken,
  getAccessToken,
  hasAccessToken,
  setAccessToken,
} from "@/lib/auth/token";
import { AUTH_TOKEN_STORAGE_KEY } from "@/lib/auth/constants";

const memoryStore: Record<string, string> = {};

const localStorageMock = {
  getItem: (key: string): string | null =>
    Object.prototype.hasOwnProperty.call(memoryStore, key)
      ? memoryStore[key]
      : null,
  setItem: (key: string, value: string): void => {
    memoryStore[key] = value;
  },
  removeItem: (key: string): void => {
    delete memoryStore[key];
  },
  clear: (): void => {
    for (const key of Object.keys(memoryStore)) {
      delete memoryStore[key];
    }
  },
};

const installWindow = (): void => {
  Object.defineProperty(globalThis, "window", {
    value: { localStorage: localStorageMock },
    writable: true,
    configurable: true,
  });
};

beforeEach(() => {
  localStorageMock.clear();
  installWindow();
});

describe("getAccessToken", () => {
  it("returns the stored JWT when localStorage has a token", () => {
    window.localStorage.setItem(AUTH_TOKEN_STORAGE_KEY, "jwt-token");
    expect(getAccessToken()).toBe("jwt-token");
  });

  it("returns null when window is unavailable", () => {
    Reflect.deleteProperty(globalThis, "window");
    expect(getAccessToken()).toBeNull();
  });
});

describe("setAccessToken", () => {
  it("stores the JWT under the auth storage key", () => {
    setAccessToken("jwt-token");
    expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe(
      "jwt-token",
    );
  });

  it("stores an empty string without treating it as a session", () => {
    setAccessToken("");
    expect(window.localStorage.getItem(AUTH_TOKEN_STORAGE_KEY)).toBe("");
    expect(hasAccessToken()).toBe(false);
  });
});

describe("clearAccessToken", () => {
  it("removes a previously stored JWT", () => {
    setAccessToken("jwt-token");
    clearAccessToken();
    expect(getAccessToken()).toBeNull();
  });

  it("does not throw when window is unavailable", () => {
    Reflect.deleteProperty(globalThis, "window");
    expect(() => clearAccessToken()).not.toThrow();
  });
});

describe("hasAccessToken", () => {
  it("returns true when a non-empty JWT is stored", () => {
    setAccessToken("jwt-token");
    expect(hasAccessToken()).toBe(true);
  });

  it("returns false when no JWT is stored", () => {
    expect(hasAccessToken()).toBe(false);
  });
});
