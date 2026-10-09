"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import {
  VALID_SUPPLIER_CATEGORIES,
  createSupplier,
  listSuppliers,
  updateSupplierRate,
  updateSupplierStatus,
  type SupplierCreatePayload,
  type SupplierRecord,
  type SupplierStatus,
} from "@/lib/suppliers";

const formatMoney = (amount: number, currency: string) =>
  `${Number(amount).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;

export const SupplierDirectory = () => {
  const [countryFilter, setCountryFilter] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("");
  const [suppliers, setSuppliers] = useState<SupplierRecord[]>([]);
  const [listStatus, setListStatus] = useState("");
  const [listKind, setListKind] = useState<"" | "ok" | "error">("");
  const [registerStatus, setRegisterStatus] = useState("");
  const [registerKind, setRegisterKind] = useState<"" | "ok" | "error">("");
  const [country, setCountry] = useState("");
  const [currency, setCurrency] = useState("");
  const [rateDrafts, setRateDrafts] = useState<Record<number, string>>({});

  const reloadSuppliers = async () => {
    setListKind("");
    setListStatus("Loading suppliers…");
    try {
      const records = await listSuppliers({
        country: countryFilter || undefined,
        category: categoryFilter || undefined,
      });
      setSuppliers(records);
      setRateDrafts(
        Object.fromEntries(records.map((supplier) => [supplier.id, String(supplier.monthly_rate)])),
      );
      setListStatus(`Showing ${records.length} supplier(s).`);
      setListKind("ok");
    } catch (error) {
      setSuppliers([]);
      setListStatus(error instanceof ApiError ? error.message : "Unable to load suppliers.");
      setListKind("error");
    }
  };

  useEffect(() => {
    let cancelled = false;

    const load = async () => {
      setListKind("");
      setListStatus("Loading suppliers…");
      try {
        const records = await listSuppliers({
          country: countryFilter || undefined,
          category: categoryFilter || undefined,
        });
        if (cancelled) {
          return;
        }
        setSuppliers(records);
        setRateDrafts(
          Object.fromEntries(
            records.map((supplier) => [supplier.id, String(supplier.monthly_rate)]),
          ),
        );
        setListStatus(`Showing ${records.length} supplier(s).`);
        setListKind("ok");
      } catch (error) {
        if (cancelled) {
          return;
        }
        setSuppliers([]);
        setListStatus(error instanceof ApiError ? error.message : "Unable to load suppliers.");
        setListKind("error");
      }
    };

    void load();
    return () => {
      cancelled = true;
    };
  }, [categoryFilter, countryFilter]);

  const handleRateUpdate = async (supplier: SupplierRecord) => {
    const monthlyRate = Number(rateDrafts[supplier.id]);
    if (!Number.isFinite(monthlyRate) || monthlyRate <= 0) {
      setListStatus("Enter a monthly rate greater than zero.");
      setListKind("error");
      return;
    }
    try {
      await updateSupplierRate(supplier.id, monthlyRate);
      setListStatus(`Updated rate for ${supplier.name}.`);
      setListKind("ok");
      await reloadSuppliers();
    } catch (error) {
      setListStatus(error instanceof ApiError ? error.message : "Rate update failed.");
      setListKind("error");
    }
  };

  const handleStatusUpdate = async (supplier: SupplierRecord) => {
    const nextStatus: SupplierStatus = supplier.status === "active" ? "suspended" : "active";
    try {
      await updateSupplierStatus(supplier.id, nextStatus);
      setListStatus(`Status updated for ${supplier.name}.`);
      setListKind("ok");
      await reloadSuppliers();
    } catch (error) {
      setListStatus(error instanceof ApiError ? error.message : "Status update failed.");
      setListKind("error");
    }
  };

  const registerSupplier = async (formData: FormData) => {
    setRegisterKind("");
    setRegisterStatus("");
    const selectedCategories = formData
      .getAll("categories")
      .map((value) => String(value))
      .filter(Boolean);
    const compliance = String(formData.get("compliance_agreement") || "");
    const renewal = String(formData.get("contract_renewal_date") || "");
    const email = String(formData.get("contact_email") || "");
    const notes = String(formData.get("notes") || "");

    const payload: SupplierCreatePayload = {
      name: String(formData.get("name") || ""),
      country: String(formData.get("country") || "") as SupplierCreatePayload["country"],
      categories: selectedCategories,
      monthly_rate: Number(formData.get("monthly_rate")),
      currency: String(formData.get("currency") || "") as SupplierCreatePayload["currency"],
      status: String(formData.get("status") || "active") as SupplierStatus,
      compliance_agreement: compliance ? (compliance as SupplierCreatePayload["compliance_agreement"]) : null,
      contract_renewal_date: renewal || null,
      contact_email: email || null,
      notes: notes || null,
    };

    try {
      await createSupplier(payload);
      setRegisterStatus("Supplier registered successfully.");
      setRegisterKind("ok");
      setCountry("");
      setCurrency("");
      await reloadSuppliers();
      return true;
    } catch (error) {
      setRegisterStatus(error instanceof ApiError ? error.message : "Registration failed.");
      setRegisterKind("error");
      return false;
    }
  };

  return (
    <div className="supplier-directory">
      <p className="eyebrow">Procurement · Compliance</p>
      <h1>Supplier directory</h1>
      <p className="home-lede">
        Authenticated writes use your existing workspace JWT. Supplier delete is not available in
        this UI.
      </p>
      <p>
        <Link href="/" className="btn-secondary">
          Back to home
        </Link>
      </p>

      <section className="supplier-filters" aria-label="Supplier filters">
        <label>
          Country
          <select
            value={countryFilter}
            onChange={(event) => setCountryFilter(event.target.value)}
          >
            <option value="">All countries</option>
            <option value="USA">USA</option>
            <option value="UK">UK</option>
          </select>
        </label>
        <label>
          Category
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
          >
            <option value="">All categories</option>
            {VALID_SUPPLIER_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <p
          role="status"
          className={listKind === "error" ? "form-error" : "field-hint"}
          aria-live="polite"
        >
          {listStatus}
        </p>
      </section>

      <section aria-labelledby="directory-heading">
        <h2 id="directory-heading">Directory</h2>
        <div className="table-scroll">
          <table className="data-table">
            <thead>
              <tr>
                {["Name", "Country", "Categories", "Monthly rate", "Compliance", "Status", "Actions"].map(
                  (heading) => (
                    <th key={heading}>{heading}</th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {suppliers.length === 0 ? (
                <tr>
                  <td colSpan={7}>No suppliers match the current filters.</td>
                </tr>
              ) : (
                suppliers.map((supplier) => (
                  <tr key={supplier.id} data-status={supplier.status}>
                    <td>{supplier.name}</td>
                    <td>{supplier.country}</td>
                    <td>{supplier.categories.join(", ")}</td>
                    <td>{formatMoney(supplier.monthly_rate, supplier.currency)}</td>
                    <td>{supplier.compliance_agreement ?? "—"}</td>
                    <td>{supplier.status}</td>
                    <td>
                      <div className="supplier-actions">
                        <input
                          type="number"
                          min="0.01"
                          step="0.01"
                          aria-label={`New monthly rate for ${supplier.name}`}
                          value={rateDrafts[supplier.id] ?? ""}
                          onChange={(event) =>
                            setRateDrafts((current) => ({
                              ...current,
                              [supplier.id]: event.target.value,
                            }))
                          }
                        />
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => void handleRateUpdate(supplier)}
                        >
                          Update rate
                        </button>
                        <button
                          type="button"
                          className="btn-secondary"
                          onClick={() => void handleStatusUpdate(supplier)}
                        >
                          {supplier.status === "active" ? "Suspend" : "Activate"}
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <section aria-labelledby="register-heading">
        <h2 id="register-heading">Register supplier</h2>
        <form
          className="supplier-register-form"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            void registerSupplier(new FormData(form)).then((registered) => {
              if (registered) {
                form.reset();
              }
            });
          }}
        >
          <label>
            Name
            <input name="name" type="text" required />
          </label>
          <label>
            Country
            <select
              name="country"
              required
              value={country}
              onChange={(event) => {
                const nextCountry = event.target.value;
                setCountry(nextCountry);
                if (nextCountry === "USA") setCurrency("USD");
                if (nextCountry === "UK") setCurrency("GBP");
              }}
            >
              <option value="">Select country</option>
              <option value="USA">USA</option>
              <option value="UK">UK</option>
            </select>
          </label>
          <label>
            Currency
            <select
              name="currency"
              required
              value={currency}
              onChange={(event) => setCurrency(event.target.value)}
            >
              <option value="">Select currency</option>
              <option value="USD">USD</option>
              <option value="GBP">GBP</option>
            </select>
          </label>
          <label>
            Monthly rate
            <input name="monthly_rate" type="number" min="0.01" step="0.01" required />
          </label>
          <label>
            Status
            <select name="status" required defaultValue="active">
              <option value="active">active</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          <label>
            Compliance agreement
            <select name="compliance_agreement" defaultValue="">
              <option value="">None</option>
              <option value="BAA">BAA</option>
              <option value="DPA">DPA</option>
              <option value="both">both</option>
            </select>
          </label>
          <label>
            Contract renewal date
            <input name="contract_renewal_date" type="date" />
          </label>
          <label>
            Contact email
            <input name="contact_email" type="email" />
          </label>
          <label className="supplier-categories">
            Categories
            <select name="categories" multiple required size={6}>
              {VALID_SUPPLIER_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
          <label className="supplier-notes">
            Notes
            <textarea name="notes" rows={3} />
          </label>
          <div className="supplier-register-actions">
            <button type="submit" className="btn-primary">Register supplier</button>
            <p
              role="status"
              className={registerKind === "error" ? "form-error" : "field-hint"}
              aria-live="polite"
            >
              {registerStatus}
            </p>
          </div>
        </form>
      </section>
    </div>
  );
};
