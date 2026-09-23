"use client";

import { FormEvent, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { ApiError } from "@/lib/auth/types";
import {
  CLINIC_IDS,
  createSupplyDelivery,
  listMedicalSupplies,
  type MedicalSupply,
} from "@/lib/inventory";
import { countryFromClinicId } from "@/lib/telemetry/mapping";
import { trackInboundOrderCreated } from "@/lib/telemetry/inventoryEvents";
import { useInventoryFlowTelemetry } from "@/lib/telemetry/useInventoryFlow";

const emptyForm = {
  supplyId: "",
  quantity: "",
  vendorName: "",
  clinicId: "",
  totalCost: "",
};

export const SupplyDeliveryForm = () => {
  const searchParams = useSearchParams();
  const presetSupplyId = searchParams.get("supply_id") ?? "";

  const [supplies, setSupplies] = useState<MedicalSupply[]>([]);
  const [formState, setFormState] = useState({
    ...emptyForm,
    supplyId: presetSupplyId,
  });
  const [isLoadingSupplies, setIsLoadingSupplies] = useState(true);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string>>({});
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  const parsedTotalCost = Number(formState.totalCost);
  const readyToSubmit =
    formState.supplyId !== "" &&
    Number(formState.quantity) > 0 &&
    formState.vendorName.trim().length > 0 &&
    formState.clinicId !== "" &&
    formState.totalCost !== "" &&
    Number.isFinite(parsedTotalCost) &&
    parsedTotalCost >= 0;

  const selectedCountry = countryFromClinicId(Number(formState.clinicId));
  const costCurrencyLabel =
    selectedCountry === "UK" ? "GBP" : selectedCountry === "US" ? "USD" : null;

  useInventoryFlowTelemetry("inbound_order", {
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

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setFormError(null);
    setFieldErrors({});
    setSuccessMessage(null);
    setIsSubmitting(true);

    try {
      const submittedTotalCost = Number(formState.totalCost);
      const delivery = await createSupplyDelivery({
        supply_id: Number(formState.supplyId),
        quantity: Number(formState.quantity),
        vendor_name: formState.vendorName.trim(),
        clinic_id: Number(formState.clinicId),
      });
      const selectedSupply = supplies.find(
        (supply) => supply.id === Number(formState.supplyId),
      );
      if (selectedSupply) {
        trackInboundOrderCreated({
          clinicId: delivery.clinic_id,
          productId: selectedSupply.id,
          liveCategory: selectedSupply.category,
          quantity: delivery.quantity,
          vendorName: delivery.vendor_name,
          inboundOrderId: delivery.id,
          totalCost: submittedTotalCost,
        });
      }
      setSubmitted(true);
      setFormState({ ...emptyForm });
      setSuccessMessage("Supply delivery recorded.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return;
      }
      if (error instanceof ApiError) {
        setFieldErrors(error.fieldErrors);
        setFormError(error.message);
      } else {
        setFormError("Unable to record the supply delivery. Try again.");
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
        <label htmlFor="delivery-supply">Medical supply</label>
        <select
          id="delivery-supply"
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
        ) : (
          <p className="field-hint">Choose by name. The supply ID is submitted for you.</p>
        )}
      </div>

      <div className="field">
        <label htmlFor="delivery-quantity">Quantity</label>
        <input
          id="delivery-quantity"
          name="quantity"
          type="number"
          min={1}
          step={1}
          required
          value={formState.quantity}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              quantity: event.target.value,
            }))
          }
          aria-invalid={Boolean(fieldErrors.quantity)}
        />
        {fieldErrors.quantity ? (
          <p className="field-error" role="alert">
            {fieldErrors.quantity}
          </p>
        ) : null}
      </div>

      <div className="field">
        <label htmlFor="delivery-vendor">Vendor name</label>
        <input
          id="delivery-vendor"
          name="vendor_name"
          type="text"
          required
          maxLength={200}
          value={formState.vendorName}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              vendorName: event.target.value,
            }))
          }
          aria-invalid={Boolean(fieldErrors.vendor_name)}
        />
        {fieldErrors.vendor_name ? (
          <p className="field-error" role="alert">
            {fieldErrors.vendor_name}
          </p>
        ) : (
          <p className="field-hint">
            Example vendors: MedLine Industries, Cardinal Health UK, Bound Tree Medical.
          </p>
        )}
      </div>

      <div className="field">
        <label htmlFor="delivery-clinic">Receiving clinic</label>
        <select
          id="delivery-clinic"
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

      <div className="field">
        <label htmlFor="delivery-total-cost">
          Total supply cost{costCurrencyLabel ? ` (${costCurrencyLabel})` : ""}
        </label>
        <input
          id="delivery-total-cost"
          name="total_cost"
          type="number"
          min={0}
          step="0.01"
          required
          value={formState.totalCost}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              totalCost: event.target.value,
            }))
          }
          aria-invalid={Boolean(fieldErrors.total_cost)}
        />
        {fieldErrors.total_cost ? (
          <p className="field-error" role="alert">
            {fieldErrors.total_cost}
          </p>
        ) : (
          <p className="field-hint">
            Cost of this inbound supply delivery in the local currency of
            the receiving clinic. US clinics use USD. UK clinics use GBP. Do
            not convert currencies.
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
        {isSubmitting ? "Recording delivery…" : "Record supply delivery"}
      </button>
    </form>
  );
};
