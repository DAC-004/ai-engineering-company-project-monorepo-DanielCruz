"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  formatCategory,
  formatCountryJurisdiction,
  getStockLevel,
  listMedicalSupplies,
  STOCK_LEVEL_LABEL,
  type MedicalSupply,
} from "@/lib/inventory";

export const MedicalSuppliesTable = () => {
  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadSupplies = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const rows = await listMedicalSupplies();
        if (!cancelled) {
          setSupplies(rows);
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
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
};
