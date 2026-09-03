"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/auth/types";
import {
  CLINIC_IDS,
  CONSUMPTION_TYPES,
  CONSUMPTION_TYPE_LABEL,
  DEPARTMENTS,
  DEPARTMENT_LABEL,
  createSupplyConsumption,
  getMedicalSupply,
  listMedicalSupplies,
  type ConsumptionType,
  type Department,
  type MedicalSupply,
} from "@/lib/inventory";
import {
  trackOutboundOrderCreated,
  trackOutboundOrderRejected,
  trackStockThresholdTriggered,
} from "@/lib/telemetry/inventoryEvents";
import { useInventoryFlowTelemetry } from "@/lib/telemetry/useInventoryFlow";

const emptyForm = {
  supplyId: "",
  quantity: "",
  consumptionType: "" as "" | ConsumptionType,
  department: "" as "" | Department,
  clinicId: "",
};

export const SupplyConsumptionForm = () => {
  const searchParams = useSearchParams();
  const presetSupplyId = searchParams.get("supply_id") ?? "";

  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [formState, setFormState] = useState({
    ...emptyForm,
    supplyId: presetSupplyId,
  });
  const [stockQuery, setStockQuery] = useState<{
    supplyId: number;
    currentStock: number | null;
    clinicStock: number | null;
    minimumStock: number | null;
    error: string | null;
  } | null>(null);
  const [isLoadingSupplies, setIsLoadingSupplies] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [quantityApiError, setQuantityApiError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const readyToSubmit =
    formState.supplyId !== "" &&
    Number(formState.quantity) > 0 &&
    formState.consumptionType !== "" &&
    formState.department !== "" &&
    formState.clinicId !== "";

  useInventoryFlowTelemetry("outbound_order", {
    productId: formState.supplyId,
    quantity: formState.quantity,
    clinicId: formState.clinicId,
    readyToSubmit,
    submitted,
  });

  useEffect(() => {
    let cancelled = false;

    const loadSupplies = async () => {
      setIsLoadingSupplies(true);
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
          setIsLoadingSupplies(false);
        }
      }
    };

    void loadSupplies();

    return () => {
      cancelled = true;
    };
  }, []);

  const selectedSupplyId = Number(formState.supplyId);
  const selectedClinicId = Number(formState.clinicId);
  const hasSelectedSupply =
    formState.supplyId !== "" && !Number.isNaN(selectedSupplyId);
  const hasSelectedClinic =
    formState.clinicId !== "" && !Number.isNaN(selectedClinicId);

  // Fetch GET /inventory/products/{id}?clinic_id= when supply and clinic are
  // selected so clinic-partitioned remaining stock is known before submit.
  useEffect(() => {
    if (!hasSelectedSupply) {
      return;
    }

    const supplyId = selectedSupplyId;
    const clinicId = hasSelectedClinic ? selectedClinicId : undefined;
    let cancelled = false;

    const loadStock = async () => {
      try {
        const supply = await getMedicalSupply(supplyId, clinicId);
        if (!cancelled) {
          setStockQuery({
            supplyId,
            currentStock: supply.current_stock,
            clinicStock: supply.clinic_current_stock,
            minimumStock: supply.minimum_stock,
            error: null,
          });
        }
      } catch (error) {
        if (cancelled) {
          return;
        }
        if (error instanceof ApiError && error.status === 401) {
          return;
        }
        setStockQuery({
          supplyId,
          currentStock: null,
          clinicStock: null,
          minimumStock: null,
          error:
            error instanceof ApiError
              ? error.message
              : "Unable to load current stock for this medical supply.",
        });
      }
    };

    void loadStock();

    return () => {
      cancelled = true;
    };
  }, [hasSelectedSupply, hasSelectedClinic, selectedSupplyId, selectedClinicId]);

  const stockMatchesSelection =
    hasSelectedSupply && stockQuery?.supplyId === selectedSupplyId;
  const selectedStock =
    stockMatchesSelection && stockQuery ? stockQuery.currentStock : null;
  const stockError =
    stockMatchesSelection && stockQuery ? stockQuery.error : null;
  const isLoadingStock = hasSelectedSupply && !stockMatchesSelection;

  const enteredQuantity = Number(formState.quantity);
  const exceedsDisplayedStock =
    selectedStock !== null &&
    formState.quantity !== "" &&
    !Number.isNaN(enteredQuantity) &&
    enteredQuantity > selectedStock;

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setQuantityApiError(null);
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const consumption = await createSupplyConsumption({
        supply_id: Number(formState.supplyId),
        quantity: Number(formState.quantity),
        consumption_type: formState.consumptionType as ConsumptionType,
        department: formState.department as Department,
        clinic_id: Number(formState.clinicId),
      });
      const selectedSupply = supplies.find(
        (supply) => supply.id === Number(formState.supplyId),
      );
      if (selectedSupply) {
        trackOutboundOrderCreated({
          clinicId: consumption.clinic_id,
          productId: selectedSupply.id,
          liveCategory: selectedSupply.category,
          quantity: consumption.quantity,
          department: consumption.department,
          outboundOrderId: consumption.id,
          consumptionReason: consumption.consumption_type as ConsumptionType,
        });
        const remainingClinicStock =
          stockQuery?.clinicStock !== null && stockQuery?.clinicStock !== undefined
            ? stockQuery.clinicStock - consumption.quantity
            : null;
        const minimumStock = stockQuery?.minimumStock ?? selectedSupply.minimum_stock;
        if (
          remainingClinicStock !== null &&
          remainingClinicStock >= 0 &&
          typeof minimumStock === "number"
        ) {
          trackStockThresholdTriggered({
            clinicId: consumption.clinic_id,
            productId: selectedSupply.id,
            liveCategory: selectedSupply.category,
            remainingQuantity: remainingClinicStock,
            minimumStock,
            triggeringOutboundOrderId: consumption.id,
          });
        }
      }
      setSubmitted(true);
      setFormState({ ...emptyForm });
      setStockQuery(null);
      setSuccessMessage("Supply consumption recorded.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return;
      }
      const selectedSupply = supplies.find(
        (supply) => supply.id === Number(formState.supplyId),
      );
      if (
        error instanceof ApiError &&
        (error.status === 400 || error.status === 422) &&
        selectedSupply &&
        formState.clinicId
      ) {
        trackOutboundOrderRejected({
          clinicId: Number(formState.clinicId),
          productId: selectedSupply.id,
          liveCategory: selectedSupply.category,
          quantity: Number(formState.quantity),
          availableQuantity: stockQuery?.clinicStock ?? stockQuery?.currentStock ?? 0,
          rejectionReason:
            error.status === 400 ? "insufficient_stock" : "validation_failed",
          department: formState.department || undefined,
        });
      }
      if (error instanceof ApiError) {
        // HTTP 400 insufficient-stock must sit next to quantity. Other FastAPI
        // field errors (typically 422) also attach to quantity when present.
        const quantityMessage = error.fieldErrors.quantity ?? null;
        if (error.status === 400 || quantityMessage) {
          setQuantityApiError(quantityMessage ?? error.message);
        }
        if (error.status !== 400) {
          setFieldErrors(error.fieldErrors);
          setFormError(error.message);
        }
      } else {
        setFormError("Unable to record the supply consumption. Try again.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  if (isLoadingSupplies) {
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

  return (
    <form className="auth-form" onSubmit={handleSubmit} noValidate>
      <div className="field">
        <label htmlFor="consumption-supply">Medical supply</label>
        <select
          id="consumption-supply"
          name="supply_id"
          required
          value={formState.supplyId}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              supplyId: event.target.value,
            }))
          }
          aria-invalid={Boolean(fieldErrors.supply_id)}
        >
          <option value="">Select a medical supply</option>
          {supplies.map((supply) => (
            <option key={supply.id} value={supply.id}>
              {supply.name}
            </option>
          ))}
        </select>
        {fieldErrors.supply_id ? (
          <p className="field-error" role="alert">
            {fieldErrors.supply_id}
          </p>
        ) : null}
      </div>

      <div className="stock-panel" aria-live="polite">
        <p className="eyebrow">Current stock</p>
        {isLoadingStock ? (
          <p className="field-hint">Retrieving current stock…</p>
        ) : stockError ? (
          <p className="field-error" role="alert">
            {stockError}
          </p>
        ) : selectedStock === null ? (
          <p className="field-hint">
            Select a medical supply to see current stock before entering a quantity.
          </p>
        ) : (
          <p className="stock-panel__value">
            {selectedStock}{" "}
            <span className="stock-panel__unit">units available</span>
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="consumption-quantity">Quantity</label>
        <input
          id="consumption-quantity"
          name="quantity"
          type="number"
          min={1}
          step={1}
          required
          value={formState.quantity}
          onChange={(event) => {
            setQuantityApiError(null);
            setFormState((current) => ({
              ...current,
              quantity: event.target.value,
            }));
          }}
          aria-invalid={Boolean(quantityApiError || fieldErrors.quantity)}
        />
        {exceedsDisplayedStock ? (
          <p className="field-warning" role="status">
            Entered quantity exceeds displayed current stock ({selectedStock}).
            You can still submit; the Inventory API enforces the stock rule.
          </p>
        ) : null}
        {quantityApiError ? (
          <p className="field-error" role="alert">
            {quantityApiError}
          </p>
        ) : fieldErrors.quantity ? (
          <p className="field-error" role="alert">
            {fieldErrors.quantity}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="consumption-type">Consumption type</label>
        <select
          id="consumption-type"
          name="consumption_type"
          required
          value={formState.consumptionType}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              consumptionType: event.target.value as "" | ConsumptionType,
            }))
          }
          aria-invalid={Boolean(fieldErrors.consumption_type)}
        >
          <option value="">Select consumption type</option>
          {CONSUMPTION_TYPES.map((consumptionType) => (
            <option key={consumptionType} value={consumptionType}>
              {CONSUMPTION_TYPE_LABEL[consumptionType]}
            </option>
          ))}
        </select>
        {fieldErrors.consumption_type ? (
          <p className="field-error" role="alert">
            {fieldErrors.consumption_type}
          </p>
        ) : (
          <p className="field-hint">Clinical use or expiry waste only.</p>
        )}
      </div>

      <div className="field">
        <label htmlFor="consumption-department">Department</label>
        <select
          id="consumption-department"
          name="department"
          required
          value={formState.department}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              department: event.target.value as "" | Department,
            }))
          }
          aria-invalid={Boolean(fieldErrors.department)}
        >
          <option value="">Select department</option>
          {DEPARTMENTS.map((department) => (
            <option key={department} value={department}>
              {DEPARTMENT_LABEL[department]}
            </option>
          ))}
        </select>
        {fieldErrors.department ? (
          <p className="field-error" role="alert">
            {fieldErrors.department}
          </p>
        ) : (
          <p className="field-hint">
            Clinical service area only. Never a patient identifier.
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="consumption-clinic">Clinic ID</label>
        <select
          id="consumption-clinic"
          name="clinic_id"
          required
          value={formState.clinicId}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              clinicId: event.target.value,
            }))
          }
          aria-invalid={Boolean(fieldErrors.clinic_id)}
        >
          <option value="">Select clinic ID</option>
          {CLINIC_IDS.map((clinicId) => (
            <option key={clinicId} value={clinicId}>
              Clinic {clinicId}
            </option>
          ))}
        </select>
        {fieldErrors.clinic_id ? (
          <p className="field-error" role="alert">
            {fieldErrors.clinic_id}
          </p>
        ) : (
          <p className="field-hint">
            Clinic IDs range from 1 to 12 (9 US clinics, 3 UK clinics).
          </p>
        )}
      </div>

      {formError ? (
        <p className="form-error" role="alert">
          {formError}
        </p>
      ) : null}
      {successMessage ? (
        <p className="form-success" role="status">
          {successMessage}
        </p>
      ) : null}

      <button type="submit" className="btn-primary" disabled={isSubmitting}>
        {isSubmitting ? "Recording consumption…" : "Record supply consumption"}
      </button>
    </form>
  );
};
