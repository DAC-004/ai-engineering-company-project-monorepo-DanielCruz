import { Suspense } from "react";

import { SupplyConsumptionForm } from "@/components/inventory/SupplyConsumptionForm";

export default function SupplyConsumptionPage() {
  return (
    <section className="home-panel inventory-panel">
      <p className="eyebrow">Inventory</p>
      <h1>Log supply consumption</h1>
      <p className="home-lede">
        Record clinical use or expiry waste. Current stock is retrieved for the
        selected medical supply before you submit. The API rejects consumption that
        would make stock negative.
      </p>
      <Suspense
        fallback={
          <div className="auth-loading" role="status" aria-live="polite">
            Loading consumption form…
          </div>
        }
      >
        <SupplyConsumptionForm />
      </Suspense>
    </section>
  );
}
