import { auditQuery, canViewAudit } from "@/lib/audit";
import type { AuthMeResponse } from "@/lib/auth/types";
jest.mock("@/lib/auth/api", () => ({ apiFetch: jest.fn() }));
const user = (role: AuthMeResponse["role"], department_id: string | null): AuthMeResponse => ({ role, department_id, department_name: null, email: "synthetic@example.com", profile: null, capabilities: ["read_audit_log"] });
test("viewer availability follows role and department without granting employee access", () => {
  expect(canViewAudit(user("admin", null))).toBe(true);
  expect(canViewAudit(user("supervisor", "clinical_operations"))).toBe(true);
  expect(canViewAudit(user("supervisor", null))).toBe(false);
  expect(canViewAudit(user("employee", "clinical_operations"))).toBe(false);
  expect(canViewAudit(null)).toBe(false);
});
test("filters and paging encode exact structural values", () => {
  const query = new URLSearchParams(auditQuery({ actor_ref: "process:support-agent", action: "patient.read", resource_ref: "opaque-id", start: "2026-11-07T00:00:00Z" }, 25));
  expect(query.get("actor_ref")).toBe("process:support-agent");
  expect(query.get("offset")).toBe("25");
  expect(query.get("resource_ref")).toBe("opaque-id");
  expect(query.get("start")).toBe("2026-11-07T00:00:00Z");
  expect(() => auditQuery({}, -1)).toThrow();
  expect(() => auditQuery({}, 0, 101)).toThrow();
});
