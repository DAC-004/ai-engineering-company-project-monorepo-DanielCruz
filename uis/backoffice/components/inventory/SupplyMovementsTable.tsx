"use client";

import { useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  formatConsumptionType,
  listInventoryOrders,
  type InventoryOrder,
} from "@/lib/inventory";

const formatCreatedAt = (isoTimestamp: string): string => {
  const parsed = new Date(isoTimestamp);
  if (Number.isNaN(parsed.getTime())) {
    return isoTimestamp;
  }
  return parsed.toLocaleString(undefined, {
    dateStyle: "medium",
    timeStyle: "short",
  });
};

const movementLabel = (order: InventoryOrder): string => {
  if (order.order_type === "delivery") {
    return "Supply delivery (inbound)";
  }
  return "Supply consumption (outbound)";
};

export const SupplyMovementsTable = () => {
  const [orders, setOrders] = useState<InventoryOrder[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadOrders = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const rows = await listInventoryOrders();
        if (!cancelled) {
          setOrders(rows);
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
            : "Unable to load supply movements.",
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadOrders();

    return () => {
      cancelled = true;
    };
  }, []);

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Loading supply movements…
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

  if (orders.length === 0) {
    return (
      <p className="field-hint" role="status">
        No supply deliveries or consumptions have been recorded yet.
      </p>
    );
  }

  return (
    <div className="table-wrap">
      <table className="data-table">
        <thead>
          <tr>
            <th scope="col">Medical supply</th>
            <th scope="col">Quantity</th>
            <th scope="col">Movement</th>
            <th scope="col">Created</th>
            <th scope="col">user_uuid</th>
            <th scope="col">Details</th>
          </tr>
        </thead>
        <tbody>
          {orders.map((order) => (
            <tr
              key={`${order.order_type}-${order.id}`}
              className={
                order.order_type === "delivery"
                  ? "movement-row movement-row--delivery"
                  : "movement-row movement-row--consumption"
              }
            >
              <td>{order.supply_name}</td>
              <td>{order.quantity}</td>
              <td>
                <span
                  className={
                    order.order_type === "delivery"
                      ? "movement-badge movement-badge--delivery"
                      : "movement-badge movement-badge--consumption"
                  }
                >
                  {movementLabel(order)}
                </span>
              </td>
              <td>{formatCreatedAt(order.created_at)}</td>
              <td>
                <code className="user-uuid">{order.user_uuid}</code>
              </td>
              <td>
                {order.order_type === "delivery" ? (
                  <>
                    Vendor name: {order.vendor_name ?? "—"}. Clinic ID:{" "}
                    {order.clinic_id}.
                  </>
                ) : (
                  <>
                    Consumption type:{" "}
                    {order.consumption_type
                      ? formatConsumptionType(order.consumption_type)
                      : "—"}
                    . Clinic ID: {order.clinic_id}.
                  </>
                )}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
