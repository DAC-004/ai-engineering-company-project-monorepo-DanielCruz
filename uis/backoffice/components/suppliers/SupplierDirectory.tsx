"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

const API_BASE = "http://127.0.0.1:8000";

const VALID_CATEGORIES = [
  "medical_supplies",
  "laboratory_services",
  "pharmaceutical",
  "clinical_software",
  "it_infrastructure",
  "hr_and_payroll_software",
  "cleaning_and_facilities",
  "patient_communication",
  "billing_and_coding_software",
  "training_platforms",
] as const;

type SupplierStatus = "active" | "suspended";

type SupplierRecord = {
  id: number;
  name: string;
  country: "USA" | "UK";
  categories: string[];
  monthly_rate: number;
  currency: "USD" | "GBP";
  status: SupplierStatus;
  compliance_agreement: "BAA" | "DPA" | "both" | null;
};

const formatMoney = (amount: number, currency: string) =>
  `${Number(amount).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })} ${currency}`;

const formatApiError = async (response: Response) => {
  const payload = (await response.json().catch(() => ({}))) as {
    detail?: string | { loc?: string[]; msg?: string }[];
  };
  if (typeof payload.detail === "string") return payload.detail;
  if (Array.isArray(payload.detail)) {
    return payload.detail
      .map((item) => {
        const location = (item.loc || []).join(".");
        return location ? `${location}: ${item.msg}` : item.msg;
      })
      .join("; ");
  }
  return `Request failed (${response.status})`;
};

export function SupplierDirectory() {
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

  const loadSuppliers = useCallback(async () => {
    const params = new URLSearchParams();
    if (countryFilter) params.set("country", countryFilter);
    if (categoryFilter) params.set("category", categoryFilter);
    const query = params.toString();
    try {
      const response = await fetch(`${API_BASE}/suppliers${query ? `?${query}` : ""}`);
      if (!response.ok) throw new Error(await formatApiError(response));
      const records = (await response.json()) as SupplierRecord[];
      setSuppliers(records);
      setRateDrafts(
        Object.fromEntries(records.map((supplier) => [supplier.id, String(supplier.monthly_rate)])),
      );
      setListStatus(`Showing ${records.length} supplier(s).`);
      setListKind("ok");
    } catch (error) {
      setSuppliers([]);
      setListStatus(error instanceof Error ? error.message : "Unable to load suppliers.");
      setListKind("error");
    }
  }, [categoryFilter, countryFilter]);

  useEffect(() => {
    const controller = new AbortController();
    const params = new URLSearchParams();
    if (countryFilter) params.set("country", countryFilter);
    if (categoryFilter) params.set("category", categoryFilter);
    const query = params.toString();

    // State updates stay in the fetch callback. The effect itself only starts the request.
    void fetch(`${API_BASE}/suppliers${query ? `?${query}` : ""}`, { signal: controller.signal })
      .then(async (response) => {
        if (!response.ok) throw new Error(await formatApiError(response));
        return (await response.json()) as SupplierRecord[];
      })
      .then((records) => {
        setSuppliers(records);
        setRateDrafts(
          Object.fromEntries(records.map((supplier) => [supplier.id, String(supplier.monthly_rate)])),
        );
        setListStatus(`Showing ${records.length} supplier(s).`);
        setListKind("ok");
      })
      .catch((error: unknown) => {
        if (error instanceof DOMException && error.name === "AbortError") return;
        setSuppliers([]);
        setListStatus(error instanceof Error ? error.message : "Unable to load suppliers.");
        setListKind("error");
      });

    return () => controller.abort();
  }, [categoryFilter, countryFilter]);

  const updateRate = async (supplier: SupplierRecord) => {
    const monthlyRate = Number(rateDrafts[supplier.id]);
    if (!(monthlyRate > 0)) {
      setListStatus("Monthly rate must be greater than zero.");
      setListKind("error");
      return;
    }
    try {
      const response = await fetch(`${API_BASE}/suppliers/${supplier.id}/rate`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ monthly_rate: monthlyRate }),
      });
      if (!response.ok) throw new Error(await formatApiError(response));
      const updated = (await response.json()) as SupplierRecord;
      setSuppliers((current) =>
        current.map((row) => (row.id === updated.id ? { ...row, ...updated } : row)),
      );
      setRateDrafts((current) => ({ ...current, [updated.id]: String(updated.monthly_rate) }));
      setListStatus(`Updated rate for ${updated.name}.`);
      setListKind("ok");
    } catch (error) {
      setListStatus(error instanceof Error ? error.message : "Update failed.");
      setListKind("error");
    }
  };

  const updateStatus = async (supplier: SupplierRecord) => {
    const nextStatus = supplier.status === "active" ? "suspended" : "active";
    try {
      const response = await fetch(`${API_BASE}/suppliers/${supplier.id}/status`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: nextStatus }),
      });
      if (!response.ok) throw new Error(await formatApiError(response));
      const updated = (await response.json()) as SupplierRecord;
      await loadSuppliers();
      setListStatus(`${updated.name} is now ${updated.status}.`);
      setListKind("ok");
    } catch (error) {
      setListStatus(error instanceof Error ? error.message : "Update failed.");
      setListKind("error");
    }
  };

  const registerSupplier = async (formData: FormData) => {
    const name = String(formData.get("name") ?? "").trim();
    const selectedCountry = String(formData.get("country") ?? "");
    const selectedCurrency = String(formData.get("currency") ?? "");
    const monthlyRate = Number(formData.get("monthly_rate"));
    const statusValue = String(formData.get("status") ?? "");
    const selectedCategories = formData.getAll("categories").map(String);
    const compliance = String(formData.get("compliance_agreement") ?? "");
    const renewal = String(formData.get("contract_renewal_date") ?? "");
    const contactEmail = String(formData.get("contact_email") ?? "").trim();
    const notes = String(formData.get("notes") ?? "").trim();

    if (!name || !selectedCountry || !selectedCurrency || !statusValue) {
      setRegisterStatus("Name, country, currency, and status are required.");
      setRegisterKind("error");
      return;
    }
    if (!selectedCategories.length) {
      setRegisterStatus("Select at least one category.");
      setRegisterKind("error");
      return;
    }
    if (!(monthlyRate > 0)) {
      setRegisterStatus("Monthly rate must be greater than zero.");
      setRegisterKind("error");
      return;
    }
    if (
      (selectedCountry === "USA" && selectedCurrency !== "USD") ||
      (selectedCountry === "UK" && selectedCurrency !== "GBP")
    ) {
      setRegisterStatus("USA requires USD and UK requires GBP.");
      setRegisterKind("error");
      return;
    }

    try {
      const response = await fetch(`${API_BASE}/suppliers`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name,
          country: selectedCountry,
          currency: selectedCurrency,
          monthly_rate: monthlyRate,
          status: statusValue,
          categories: selectedCategories,
          compliance_agreement: compliance || null,
          contract_renewal_date: renewal || null,
          contact_email: contactEmail || null,
          notes: notes || null,
        }),
      });
      if (!response.ok) throw new Error(await formatApiError(response));
      setRegisterStatus("Supplier registered successfully.");
      setRegisterKind("ok");
      setCountry("");
      setCurrency("");
      await loadSuppliers();
      return true;
    } catch (error) {
      setRegisterStatus(error instanceof Error ? error.message : "Registration failed.");
      setRegisterKind("error");
      return false;
    }
  };

  return (
    <main className="bo-shell py-8">
      <p className="text-sm font-semibold uppercase tracking-[0.18em] text-(--bo-accent)">
        Procurement · Compliance
      </p>
      <h1 className="mt-2 text-3xl font-bold">Supplier Directory</h1>
      <p className="mt-3 max-w-3xl text-(--bo-muted)">
        Single source of truth for clinical, operational, and technology suppliers across USA and UK clinics.
      </p>
      <p className="mt-4">
        <Link href="/" className="text-sm font-semibold text-(--bo-accent)">
          Back to operations overview
        </Link>
      </p>

      <section className="mt-8 flex flex-wrap items-end gap-4" aria-label="Supplier filters">
        <label className="flex flex-col gap-1 text-sm font-medium">
          Country
          <select
            value={countryFilter}
            onChange={(event) => setCountryFilter(event.target.value)}
            className="rounded-xl border border-(--bo-line) bg-white px-3 py-2"
          >
            <option value="">All countries</option>
            <option value="USA">USA</option>
            <option value="UK">UK</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm font-medium">
          Category
          <select
            value={categoryFilter}
            onChange={(event) => setCategoryFilter(event.target.value)}
            className="rounded-xl border border-(--bo-line) bg-white px-3 py-2"
          >
            <option value="">All categories</option>
            {VALID_CATEGORIES.map((category) => (
              <option key={category} value={category}>
                {category}
              </option>
            ))}
          </select>
        </label>
        <p
          role="status"
          className={listKind === "error" ? "text-sm text-red-700" : "text-sm text-(--bo-muted)"}
        >
          {listStatus}
        </p>
      </section>

      <section className="mt-8" aria-labelledby="directory-heading">
        <h2 id="directory-heading" className="text-xl font-semibold">
          Directory
        </h2>
        <div className="mt-3 overflow-x-auto rounded-2xl border border-(--bo-line) bg-white">
          <table className="min-w-full text-left text-sm">
            <thead className="bg-(--bo-accent-soft)">
              <tr>
                {["Name", "Country", "Categories", "Monthly rate", "Compliance", "Status", "Actions"].map(
                  (heading) => (
                    <th key={heading} className="px-3 py-2 font-semibold">
                      {heading}
                    </th>
                  ),
                )}
              </tr>
            </thead>
            <tbody>
              {suppliers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4">
                    No suppliers match the current filters.
                  </td>
                </tr>
              ) : (
                suppliers.map((supplier) => (
                  <tr
                    key={supplier.id}
                    className={
                      supplier.status === "active" ? "border-t border-(--bo-line)" : "border-t border-(--bo-line) bg-amber-50"
                    }
                  >
                    <td className="px-3 py-3">{supplier.name}</td>
                    <td className="px-3 py-3">{supplier.country}</td>
                    <td className="px-3 py-3">{supplier.categories.join(", ")}</td>
                    <td className="px-3 py-3">{formatMoney(supplier.monthly_rate, supplier.currency)}</td>
                    <td className="px-3 py-3">{supplier.compliance_agreement ?? "—"}</td>
                    <td className="px-3 py-3">
                      <span
                        className={
                          supplier.status === "active"
                            ? "rounded-full bg-emerald-100 px-2 py-1 text-xs font-semibold text-emerald-800"
                            : "rounded-full bg-amber-200 px-2 py-1 text-xs font-semibold text-amber-900"
                        }
                      >
                        {supplier.status}
                      </span>
                    </td>
                    <td className="px-3 py-3">
                      <div className="flex flex-wrap items-center gap-2">
                        <input
                          type="number"
                          min="0.01"
                          step="0.01"
                          aria-label={`New monthly rate for ${supplier.name}`}
                          value={rateDrafts[supplier.id] ?? ""}
                          onChange={(event) =>
                            setRateDrafts((current) => ({ ...current, [supplier.id]: event.target.value }))
                          }
                          className="w-28 rounded-lg border border-(--bo-line) px-2 py-1"
                        />
                        <button
                          type="button"
                          onClick={() => void updateRate(supplier)}
                          className="rounded-lg border border-(--bo-line) px-2 py-1"
                        >
                          Update rate
                        </button>
                        <button
                          type="button"
                          onClick={() => void updateStatus(supplier)}
                          className="rounded-lg border border-(--bo-line) px-2 py-1"
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

      <section className="mt-8" aria-labelledby="register-heading">
        <h2 id="register-heading" className="text-xl font-semibold">
          Register supplier
        </h2>
        <form
          className="mt-3 grid gap-4 rounded-2xl border border-(--bo-line) bg-white p-4 md:grid-cols-2"
          onSubmit={(event) => {
            event.preventDefault();
            const form = event.currentTarget;
            void registerSupplier(new FormData(form)).then((registered) => {
              if (registered) form.reset();
            });
          }}
        >
          <label className="flex flex-col gap-1 text-sm font-medium">
            Name
            <input name="name" type="text" required className="rounded-lg border border-(--bo-line) px-3 py-2" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
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
              className="rounded-lg border border-(--bo-line) px-3 py-2"
            >
              <option value="">Select country</option>
              <option value="USA">USA</option>
              <option value="UK">UK</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Currency
            <select
              name="currency"
              required
              value={currency}
              onChange={(event) => setCurrency(event.target.value)}
              className="rounded-lg border border-(--bo-line) px-3 py-2"
            >
              <option value="">Select currency</option>
              <option value="USD">USD</option>
              <option value="GBP">GBP</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Monthly rate
            <input
              name="monthly_rate"
              type="number"
              min="0.01"
              step="0.01"
              required
              className="rounded-lg border border-(--bo-line) px-3 py-2"
            />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Status
            <select name="status" required className="rounded-lg border border-(--bo-line) px-3 py-2">
              <option value="active">active</option>
              <option value="suspended">suspended</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Compliance agreement
            <select name="compliance_agreement" className="rounded-lg border border-(--bo-line) px-3 py-2">
              <option value="">None</option>
              <option value="BAA">BAA</option>
              <option value="DPA">DPA</option>
              <option value="both">both</option>
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Contract renewal date
            <input name="contract_renewal_date" type="date" className="rounded-lg border border-(--bo-line) px-3 py-2" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium">
            Contact email
            <input name="contact_email" type="email" className="rounded-lg border border-(--bo-line) px-3 py-2" />
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium md:col-span-2">
            Categories
            <select
              name="categories"
              multiple
              required
              size={6}
              className="rounded-lg border border-(--bo-line) px-3 py-2"
            >
              {VALID_CATEGORIES.map((category) => (
                <option key={category} value={category}>
                  {category}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col gap-1 text-sm font-medium md:col-span-2">
            Notes
            <textarea name="notes" rows={3} className="rounded-lg border border-(--bo-line) px-3 py-2" />
          </label>
          <div>
            <button type="submit" className="rounded-full bg-(--bo-accent) px-4 py-2 text-sm font-semibold text-white">
              Register supplier
            </button>
            <p
              role="status"
              className={registerKind === "error" ? "mt-2 text-sm text-red-700" : "mt-2 text-sm text-(--bo-muted)"}
            >
              {registerStatus}
            </p>
          </div>
        </form>
      </section>
    </main>
  );
}
