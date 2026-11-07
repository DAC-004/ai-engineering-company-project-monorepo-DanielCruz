import { canStartRfpResponse } from "@/lib/rfp";

describe("response start and recovery", () => {
  it("allows initial intake and stale interrupted response states", () => {
    expect(canStartRfpResponse({ status: "intake_complete", stalled: false, part3_handoff: null })).toBe(true);
    for (const status of ["drafting", "under_evaluation"]) {
      expect(canStartRfpResponse({ status, stalled: true, part3_handoff: null })).toBe(true);
      expect(canStartRfpResponse({ status, stalled: false, part3_handoff: null })).toBe(false);
    }
  });
  it("does not restart completed responses or unrelated states", () => {
    expect(canStartRfpResponse({ status: "under_evaluation", stalled: true, part3_handoff: { response_complete: true } })).toBe(false);
    for (const status of ["analyzing", "discarded", "waiting_for_approval", "done"]) {
      expect(canStartRfpResponse({ status, stalled: true, part3_handoff: null })).toBe(false);
    }
  });
});
