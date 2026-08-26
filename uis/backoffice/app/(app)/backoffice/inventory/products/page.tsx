import { MedicalSuppliesTable } from "@/components/inventory/MedicalSuppliesTable";

export default function MedicalSuppliesPage() {
  return (
    <section className="home-panel inventory-panel">
      <p className="eyebrow">Inventory</p>
      <h1>Medical supplies</h1>
      <p className="home-lede">
        Current stock is computed by the Inventory API from supply deliveries minus
        supply consumptions. Direct stock edits are not allowed.
      </p>
      <MedicalSuppliesTable />
    </section>
  );
}
