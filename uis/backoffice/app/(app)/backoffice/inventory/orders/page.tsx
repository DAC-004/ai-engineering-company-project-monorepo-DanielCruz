import { SupplyMovementsTable } from "@/components/inventory/SupplyMovementsTable";

export default function SupplyMovementsPage() {
  return (
    <section className="home-panel inventory-panel">
      <p className="eyebrow">Inventory</p>
      <h1>Supply movements</h1>
      <p className="home-lede">
        Read-only history of supply deliveries (inbound) and supply consumptions
        (outbound). Movements cannot be edited or deleted from this view.
      </p>
      <SupplyMovementsTable />
    </section>
  );
}
