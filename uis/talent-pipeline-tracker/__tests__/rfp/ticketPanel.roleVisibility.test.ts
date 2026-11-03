/**
 * RfpTicketPanel canApprove is role visibility only. Workflow state conditions stay intact.
 */

import { readFileSync } from "node:fs";
import { join } from "node:path";

import { canUpdateDepartmentRecord } from "@/lib/auth/capabilities";

describe("canApprove role definition", () => {
  it("allows supervisor and admin and denies employee", () => {
    expect(canUpdateDepartmentRecord("employee")).toBe(false);
    expect(canUpdateDepartmentRecord("supervisor")).toBe(true);
    expect(canUpdateDepartmentRecord("admin")).toBe(true);
    expect(canUpdateDepartmentRecord(null)).toBe(false);
    expect(canUpdateDepartmentRecord(undefined)).toBe(false);
  });
});

describe("RfpTicketPanel role visibility conditions", () => {
  const panel = readFileSync(
    join(
      __dirname,
      "..",
      "..",
      "components",
      "rfp",
      "RfpTicketPanel.tsx",
    ),
    "utf8",
  );

  it("defines canApprove from the existing update-capability helper", () => {
    expect(panel).toContain(
      "const canApprove = canUpdateDepartmentRecord(currentUser?.role);",
    );
  });

  it("keeps readyToStartApproval and waiting-state conditions behind canApprove", () => {
    expect(panel).toContain("{readyToStartApproval(ticket) && canApprove ? (");
    expect(panel).toContain("{waiting && canApprove ? (");
    expect(panel).toContain(
      'const waiting = ticket.status === "waiting_for_approval" && section.approval_status !== "approved";',
    );
  });

  it("retains the existing Approve decision handler", () => {
    expect(panel).toContain('handleDecision(section.department_id, "approve")');
  });
});
