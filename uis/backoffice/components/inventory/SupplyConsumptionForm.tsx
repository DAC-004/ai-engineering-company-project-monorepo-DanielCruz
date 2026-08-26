"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/auth/types";
import {
  CLINIC_IDS,
  CONSUMPTION_TYPES,
  CONSUMPTION_TYPE_LABEL,
  createSupplyConsumption,
  getMedicalSupply,
  listMedicalSupplies,
  type ConsumptionType,
  type MedicalSupply,
} from "@/lib/inventory";

const emptyForm = {
  supplyId: "",
  quantity: "",
  consumptionType: "" as "" | ConsumptionType,
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
    error: string | null;
  } | null>(null);
  const [isLoadingSupplies, setIsLoadingSupplies] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [quantityApiError, setQuantityApiError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

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
  const hasSelectedSupply =
    formState.supplyId !== "" && !Number.isNaN(selectedSupplyId);

  // Fetch GET /inventory/products/{id} whenever the selected medical supply
  // changes so current_stock is shown before quantity entry. The list payload
  // is not treated as authoritative after selection.
  useEffect(() => {
    if (!hasSelectedSupply) {
      return;
    }

    const supplyId = selectedSupplyId;
    let cancelled = false;

    const loadStock = async () => {
      try {
        const supply = await getMedicalSupply(supplyId);
        if (!cancelled) {
          setStockQuery({
            supplyId,
            currentStock: supply.current_stock,
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
  }, [hasSelectedSupply, selectedSupplyId]);

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
      await createSupplyConsumption({
        supply_id: Number(formState.supplyId),
        quantity: Number(formState.quantity),
        consumption_type: formState.consumptionType as ConsumptionType,
        clinic_id: Number(formState.clinicId),
      });
      setFormState({ ...emptyForm });
      setStockQuery(null);
      setSuccessMessage("Supply consumption recorded.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return;
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
