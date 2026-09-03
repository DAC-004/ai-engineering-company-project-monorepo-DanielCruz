"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  CLINIC_IDS,
  attemptDirectStockEdit,
  formatCategory,
  formatCountryJurisdiction,
  getStockLevel,
  listInventoryOrders,
  listMedicalSupplies,
  STOCK_LEVEL_LABEL,
  type MedicalSupply,
} from "@/lib/inventory";
import {
  trackDirectStockEditRejected,
  trackSupplyExpiryFlagged,
} from "@/lib/telemetry/inventoryEvents";

export const MedicalSuppliesTable = () => {
  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [stockEdit, setStockEdit] = useState<{
    supplyId: number;
    clinicId: string;
    quantity: string;
  } | null>(null);
  const [stockEditError, setStockEditError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadSupplies = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const [rows, orders] = await Promise.all([
          listMedicalSupplies(),
          listInventoryOrders(),
        ]);
        if (!cancelled) {
          setSupplies(rows);
          const remainingByProductClinic = new Map<string, number>();
          for (const order of orders) {
            const key = `${order.supply_id}:${order.clinic_id}`;
            const current = remainingByProductClinic.get(key) ?? 0;
            const delta =
              order.order_type === "delivery" ? order.quantity : -order.quantity;
            remainingByProductClinic.set(key, current + delta);
          }
          for (const supply of rows) {
            if (!supply.expiry_date) {
              continue;
            }
            let holdingClinicId: number | null = null;
            let holdingQuantity = -1;
            for (const clinicId of CLINIC_IDS) {
              const remaining =
                remainingByProductClinic.get(`${supply.id}:${clinicId}`) ?? 0;
              if (remaining > holdingQuantity) {
                holdingQuantity = remaining;
                holdingClinicId = clinicId;
              }
            }
            if (holdingClinicId !== null && holdingQuantity > 0) {
              trackSupplyExpiryFlagged({
                clinicId: holdingClinicId,
                productId: supply.id,
                liveCategory: supply.category,
                quantity: holdingQuantity,
                expiryDate: supply.expiry_date,
              });
            }
          }
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          return;
        }
        setLoadError(
          error instanceof ApiError
            ? error.message
            : "Unable to load medical supplies.",
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadSupplies();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleDirectStockEdit = async (supply: MedicalSupply) => {
    if (!stockEdit || stockEdit.supplyId !== supply.id) {
      return;
    }
    setStockEditError(null);
    const clinicId = Number(stockEdit.clinicId);
    const attemptedQuantity = Number(stockEdit.quantity);
    if (
      Number.isNaN(clinicId) ||
      Number.isNaN(attemptedQuantity) ||
      stockEdit.clinicId === "" ||
      stockEdit.quantity === ""
    ) {
      setStockEditError("Select a clinic and an attempted stock value.");
      return;
    }
    try {
      await attemptDirectStockEdit(supply.id, {
        clinic_id: clinicId,
        current_stock: attemptedQuantity,
      });
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return;
      }
      if (
        error instanceof ApiError &&
        (error.status === 405 || error.status === 400)
      ) {
        trackDirectStockEditRejected({
          clinicId,
          productId: supply.id,
          liveCategory: supply.category,
          attemptedQuantity,
          httpMethod: "PATCH",
          rejectionReason:
            error.status === 400 ? "stock_field_forbidden" : "method_not_allowed",
        });
        setStockEditError(
          "Direct stock edits are rejected. Use a supply delivery or consumption.",
        );
        return;
      }
      setStockEditError(
        error instanceof ApiError
          ? error.message
          : "Unable to submit the stock change.",
      );
    }
  };

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Loading medical supplies…
      </div>
    );
  }

  if (loadError) {
    return (
      <p className="form-error" role="alert">
        {loadError}
      </p>
    );
  }

  if (supplies.length === 0) {
    return (
      <p className="field-hint" role="status">
        No medical supplies are registered yet.
      </p>
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Medical supply</th>
            <th scope="col">SKU</th>
            <th scope="col">Category</th>
            <th scope="col">Unit</th>
            <th scope="col">Regulatory jurisdiction</th>
            <th scope="col">Current stock</th>
            <th scope="col">Actions</th>
          </tr>
        </thead>
        <tbody>
          {supplies.map((supply) => {
            const stockLevel = getStockLevel(supply.current_stock);
            return (
              <tr key={supply.id}>
                <td>{supply.name}</td>
                <td>
                  <code className="sku">{supply.sku}</code>
                </td>
                <td>{formatCategory(supply.category)}</td>
                <td>{supply.unit}</td>
                <td>{formatCountryJurisdiction(supply.country)}</td>
                <td>
                  <span className={`stock-badge stock-badge--${stockLevel}`}>
                    <span className="stock-badge__value">
                      {supply.current_stock}
                    </span>
                    <span className="stock-badge__label">
                      {STOCK_LEVEL_LABEL[stockLevel]}
                    </span>
                  </span>
                </td>
                <td>
                  <div className="row-actions">
                    <Link
                      href={`/backoffice/inventory/orders/inbound?supply_id=${supply.id}`}
                      className="row-action"
                    >
                      Log supply delivery
                    </Link>
                    <Link
                      href={`/backoffice/inventory/orders/outbound?supply_id=${supply.id}`}
                      className="row-action"
                    >
                      Log supply consumption
                    </Link>
                    <button
                      type="button"
                      className="row-action"
                      onClick={() =>
                        setStockEdit({
                          supplyId: supply.id,
                          clinicId: "",
                          quantity: "",
                        })
                      }
                    >
                      Set stock
                    </button>
                  </div>
                  {stockEdit?.supplyId === supply.id ? (
                    <form
                      className="auth-form"
                      onSubmit={(event) => {
                        event.preventDefault();
                        void handleDirectStockEdit(supply);
                      }}
                    >
                      <p className="field-hint">
                        Stock is computed from orders. This request is rejected
                        on purpose.
                      </p>
                      <label htmlFor={`stock-clinic-${supply.id}`}>Clinic</label>
                      <select
                        id={`stock-clinic-${supply.id}`}
                        value={stockEdit.clinicId}
                        onChange={(event) =>
                          setStockEdit({
                            ...stockEdit,
                            clinicId: event.target.value,
                          })
                        }
                        required
                      >
                        <option value="">Select clinic</option>
                        {CLINIC_IDS.map((clinicId) => (
                          <option key={clinicId} value={clinicId}>
                            Clinic {clinicId}
                          </option>
                        ))}
                      </select>
                      <label htmlFor={`stock-qty-${supply.id}`}>
                        Attempted stock
                      </label>
                      <input
                        id={`stock-qty-${supply.id}`}
                        type="number"
                        value={stockEdit.quantity}
                        onChange={(event) =>
                          setStockEdit({
                            ...stockEdit,
                            quantity: event.target.value,
                          })
                        }
                        required
                      />
                      {stockEditError ? (
                        <p className="field-error" role="alert">
                          {stockEditError}
                        </p>
                      ) : null}
                      <button type="submit" className="btn-secondary">
                        Submit stock change
                      </button>
                    </form>
                  ) : null}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
