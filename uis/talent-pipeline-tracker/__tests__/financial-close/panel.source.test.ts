import {
  amountStatusLabel,
  contributorLabel,
  isNamedTomReviewer,
  lineLabel,
  moneyText,
  TOM_CLOSE_DEPARTMENT,
  TOM_CLOSE_EMAIL,
  TOM_CLOSE_ROLE,
} from "@/lib/financialClose";

describe("named Tom reviewer identity", () => {
  it("requires email, supervisor role, and revenue-cycle department together", () => {
    expect(
      isNamedTomReviewer({
        email: TOM_CLOSE_EMAIL,
        role: TOM_CLOSE_ROLE,
        department_id: TOM_CLOSE_DEPARTMENT,
      }),
    ).toBe(true);
    expect(
      isNamedTomReviewer({
        email: TOM_CLOSE_EMAIL,
        role: "admin",
        department_id: TOM_CLOSE_DEPARTMENT,
      }),
    ).toBe(false);
    expect(
      isNamedTomReviewer({
        email: TOM_CLOSE_EMAIL,
        role: TOM_CLOSE_ROLE,
        department_id: "technology",
      }),
    ).toBe(false);
    expect(
      isNamedTomReviewer({
        email: "james.admin@healthcore.example",
        role: TOM_CLOSE_ROLE,
        department_id: TOM_CLOSE_DEPARTMENT,
      }),
    ).toBe(false);
  });

  it("labels known subtotals as incomplete", () => {
    expect(amountStatusLabel({ amount_status: "known_subtotal" })).toBe(
      "known subtotal, incomplete",
    );
    expect(amountStatusLabel({ missing_actual: true })).toBe("actual missing");
  });
});

describe("rendered close report labels", () => {
  it("shows country, payer, currency, percent, and incomplete status for a line", () => {
    const label = lineLabel({
      line_id: "us_laboratory",
      country: "United States",
      payer: "n/a",
      currency: "USD",
      verified_actual: "48150",
      budget: "45000",
      percent_display: "7.0%",
      amount_status: "complete",
    });
    expect(label).toContain("United States");
    expect(label).toContain("n/a");
    expect(label).toContain("USD");
    expect(label).toContain("actual 48150");
    expect(label).toContain("budget 45000");
    expect(label).toContain("7.0%");
    expect(label).toContain("complete");
  });

  it("labels missing actuals and known subtotals in consolidated wording", () => {
    expect(moneyText(null, "incomplete")).toBe("incomplete");
    expect(
      lineLabel({
        line_id: "us_rent",
        country: "United States",
        payer: "n/a",
        currency: "USD",
        verified_actual: "179000",
        budget: "180000",
        amount_status: "known_subtotal",
        incomplete: true,
      }),
    ).toContain("known subtotal, incomplete");
  });

  it("shows contributing row ids, source refs, and values for lookup", () => {
    const label = contributorLabel(
      {
        row_id: "LED-202610-027",
        ingest_ref: "ingest.ledger.27",
        source_refs: ["ledger.csv:27"],
        value: "19.26",
      },
      0,
    );
    expect(label).toContain("LED-202610-027");
    expect(label).toContain("ingest.ledger.27");
    expect(label).toContain("ledger.csv:27");
    expect(label).toContain("19.26");
  });
});

describe("derived financial figure references", () => {
  it("names the producing source figure so a reviewer can continue the trace", () => {
    expect(contributorLabel({ source_figure_id: "us_laboratory.budget" }, 0))
      .toContain("us_laboratory.budget");
    expect(contributorLabel({ source_figure_id: "uk_private_revenue.verified_actual" }, 0))
      .toContain("uk_private_revenue.verified_actual");
  });
});
