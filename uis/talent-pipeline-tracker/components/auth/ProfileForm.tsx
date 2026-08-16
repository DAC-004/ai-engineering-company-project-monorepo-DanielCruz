"use client";

import { FormEvent, useEffect, useState } from "react";

import { ApiError } from "@/lib/auth/types";
import { fetchCurrentUser, updateMyProfile } from "@/lib/auth/session";

type ProfileFormState = {
  email: string;
  name: string;
  phone: string;
  address: string;
};

export const ProfileForm = () => {
  const [formState, setFormState] = useState<ProfileFormState>({
    email: "",
    name: "",
    phone: "",
    address: "",
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    const loadProfile = async () => {
      setIsLoading(true);
      setLoadError(null);

      try {
        const me = await fetchCurrentUser();
        if (cancelled) {
          return;
        }

        setFormState({
          email: me.email,
          name: me.profile?.name ?? "",
          phone: me.profile?.phone ?? "",
          address: me.profile?.address ?? "",
        });
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
            : "Unable to load profile information.",
        );
      } finally {
        if (!cancelled) {
          setIsLoading(false);
        }
      }
    };

    void loadProfile();

    return () => {
      cancelled = true;
    };
  }, []);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    setSaveSuccess(null);
    setIsSaving(true);

    try {
      const updated = await updateMyProfile({
        name: formState.name.trim() || null,
        phone: formState.phone.trim() || null,
        address: formState.address.trim() || null,
      });

      setFormState((current) => ({
        ...current,
        name: updated.name ?? "",
        phone: updated.phone ?? "",
        address: updated.address ?? "",
      }));
      setSaveSuccess("Profile updated.");
    } catch (error) {
      if (error instanceof ApiError && error.status === 401) {
        return;
      }
      setSaveError(
        error instanceof ApiError
          ? error.message
          : "Unable to update profile. Try again.",
      );
    } finally {
      setIsSaving(false);
    }
  };

  if (isLoading) {
    return (
      <div className="auth-loading" role="status" aria-live="polite">
        Loading profile…
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
    <form className="auth-form profile-form" onSubmit={handleSubmit}>
      <div className="field">
        <label htmlFor="profile-email">Email</label>
        <input
          id="profile-email"
          name="email"
          type="email"
          value={formState.email}
          readOnly
          disabled
        />
        <p className="field-hint">Email comes from the User account (GET /auth/me).</p>
      </div>

      <div className="field">
        <label htmlFor="profile-name">Name</label>
        <input
          id="profile-name"
          name="name"
          type="text"
          autoComplete="name"
          value={formState.name}
          onChange={(event) =>
            setFormState((current) => ({ ...current, name: event.target.value }))
          }
        />
      </div>

      <div className="field">
        <label htmlFor="profile-phone">Phone</label>
        <input
          id="profile-phone"
          name="phone"
          type="tel"
          autoComplete="tel"
          value={formState.phone}
          onChange={(event) =>
            setFormState((current) => ({ ...current, phone: event.target.value }))
          }
        />
      </div>

      <div className="field">
        <label htmlFor="profile-address">Address</label>
        <input
          id="profile-address"
          name="address"
          type="text"
          autoComplete="street-address"
          value={formState.address}
          onChange={(event) =>
            setFormState((current) => ({
              ...current,
              address: event.target.value,
            }))
          }
        />
      </div>

      {saveError ? (
        <p className="form-error" role="alert">
          {saveError}
        </p>
      ) : null}
      {saveSuccess ? (
        <p className="form-success" role="status">
          {saveSuccess}
        </p>
      ) : null}

      <button type="submit" className="btn-primary" disabled={isSaving}>
        {isSaving ? "Saving…" : "Save profile"}
      </button>
    </form>
  );
};
