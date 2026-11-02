/**
 * Admin-only account creation page: source and form-lifecycle helpers.
 * Isolated fixtures; no persistent account writes.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { ApiError } from "@/lib/auth/types";
import {
  AMBIGUOUS_CREATE_MESSAGE,
  REPEAT_AFTER_SUCCESS_MESSAGE,
  createRequestSignature,
  decideCreateSubmit,
  messageForCreateFailure,
} from "@/lib/access/createAccountForm";
import { canManageAccess } from "@/lib/auth/capabilities";

const trackerRoot = join(__dirname, "..", "..");

const readTracker = (...segments: string[]): string =>
  readFileSync(join(trackerRoot, ...segments), "utf8");

describe("Admin-only creation capability", () => {
  it("allows only admin", () => {
    expect(canManageAccess("admin")).toBe(true);
    expect(canManageAccess("employee")).toBe(false);
    expect(canManageAccess("supervisor")).toBe(false);
    expect(canManageAccess(null)).toBe(false);
  });
});

describe("create account page source", () => {
  const page = readTracker("app", "(app)", "backoffice", "access", "create", "page.tsx");
  const access = readTracker("lib", "access.ts");
  const shell = readTracker("components", "auth", "AppShell.tsx");
  const home = readTracker("app", "(app)", "page.tsx");
  const assignmentPage = readTracker("app", "(app)", "backoffice", "access", "page.tsx");

  it("uses existing Admin POST /users helper and independent catalogs", () => {
    expect(access).toContain('apiFetch<UserPublic>("/users"');
    expect(access).toContain("method: \"POST\"");
    expect(page).toContain("createAdminUser");
    expect(page).toContain("listRoles()");
    expect(page).toContain("listDepartments()");
    expect(page).toContain('name="role_id"');
    expect(page).toContain('name="department_id"');
  });

  it("does not hardcode the approved demo identity", () => {
    expect(page).not.toContain("orders.quoteflow@gmail.com");
    expect(page).not.toContain("cruzdaniel004@gmail.com");
  });

  it("denies non-admins with the established permission message", () => {
    expect(page).toContain("canManageAccess(currentUser?.role)");
    expect(page).toContain("Insufficient role permissions");
  });

  it("keeps public registration disabled", () => {
    expect(page).not.toContain('href="/register"');
    expect(page).not.toContain("registerAndAuthenticate");
  });

  it("exposes Admin navigation only behind the access-admin gate", () => {
    expect(shell).toContain('href="/backoffice/access/create"');
    expect(shell).toContain("{isAccessAdmin ? (");
    expect(home).toContain('href="/backoffice/access/create"');
    expect(assignmentPage).toContain('href="/backoffice/access/create"');
    expect(assignmentPage).toContain("Independent assignment");
  });

  it("clears password on success, failure, cancel, and unmount", () => {
    expect(page).toContain("clearPassword()");
    expect(page).toContain('setPassword("")');
    expect(page).toContain('autoComplete="new-password"');
    expect(page).not.toContain("localStorage");
    expect(page).not.toContain("sessionStorage");
    expect(page).not.toContain("track(");
  });

  it("does not claim success before the API response or reverse an in-flight request", () => {
    expect(page).toContain("Account created:");
    expect(page).toContain("created.email");
    expect(page).toContain("A create request is already in progress and cannot be reversed here.");
    expect(page).toContain("Creation cancelled. No request was sent.");
    expect(page).toContain("disabled={pending}");
    expect(page).toContain("submitInFlightRef");
    expect(page).toContain("inFlight: submitInFlightRef.current");
  });
});

describe("create account submit lifecycle", () => {
  it("blocks duplicate in-flight submits", () => {
    expect(
      decideCreateSubmit({
        pending: true,
        lastSuccessSignature: null,
        nextSignature: "a|admin|technology",
      }),
    ).toBe("pending");
    expect(
      decideCreateSubmit({
        pending: false,
        inFlight: true,
        lastSuccessSignature: null,
        nextSignature: "a|admin|technology",
      }),
    ).toBe("pending");
  });

  it("blocks unchanged repeat after success", () => {
    const signature = createRequestSignature({
      email: "new.user@healthcore.example",
      roleId: "admin",
      departmentId: "technology",
    });
    expect(
      decideCreateSubmit({
        pending: false,
        lastSuccessSignature: signature,
        nextSignature: signature,
      }),
    ).toBe("repeat");
    expect(REPEAT_AFTER_SUCCESS_MESSAGE).toContain("already created");
  });

  it("allows a new identity after success", () => {
    expect(
      decideCreateSubmit({
        pending: false,
        lastSuccessSignature: "one@healthcore.example|employee|technology",
        nextSignature: "two@healthcore.example|employee|technology",
      }),
    ).toBe("submit");
  });

  it("treats network failure as ambiguous and does not claim the account was not created", () => {
    const failure = messageForCreateFailure(new ApiError("unreachable", 0));
    expect(failure.ambiguous).toBe(true);
    expect(failure.message).toBe(AMBIGUOUS_CREATE_MESSAGE);
    expect(failure.message.toLowerCase()).not.toContain("was not created");
  });

  it("preserves API duplicate and authorization messages", () => {
    const duplicate = messageForCreateFailure(
      new ApiError("A user with this email already exists.", 409),
    );
    expect(duplicate.ambiguous).toBe(false);
    expect(duplicate.message).toBe("A user with this email already exists.");
    const denied = messageForCreateFailure(
      new ApiError("Insufficient role permissions", 403),
    );
    expect(denied.message).toBe("Insufficient role permissions");
  });
});
