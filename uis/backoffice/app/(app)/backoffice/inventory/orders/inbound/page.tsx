import { Suspense } from "react";

import { SupplyDeliveryForm } from "@/components/inventory/SupplyDeliveryForm";

export default function SupplyDeliveryPage() {
  return (
    <section className="home-panel inventory-panel">
      <p className="eyebrow">Inventory</p>
      <h1>Log supply delivery</h1>
      <p className="home-lede">
        Record a vendor shipment received at a HealthCore clinic. The authenticated
        staff member is stored as user_uuid by the API.
      </p>
      <Suspense
        fallback={
          <div className="auth-loading" role="status" aria-live="polite">
            Loading delivery form…
          </div>
        }
      >
        <SupplyDeliveryForm />
      </Suspense>
    </section>
  );
}
