"use client";

import Link from "next/link";

const STORAGE_KEY = "healthcore.rfp.recentTickets";

const readRecentTicketIds = (): string[] => {
  if (typeof window === "undefined") {
    return [];
  }
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? (JSON.parse(raw) as unknown) : [];
    if (!Array.isArray(parsed)) {
      return [];
    }
    return parsed.filter((value): value is string => typeof value === "string" && value.length > 0);
  } catch {
    return [];
  }
};

/**
 * Reopen tickets visited in this browser without typing a URL.
 * Arrival stream covers live creates; this covers return visits after refresh.
 */
export const RfpRecentTickets = () => {
  const ticketIds = readRecentTicketIds();

  if (ticketIds.length === 0) {
    return null;
  }

  return (
    <section className="rfp-recent-panel" aria-label="Recent RFP tickets">
      <h2>Recent tickets</h2>
      <p className="home-lede">Open a ticket you already reviewed in this browser.</p>
      <ul className="rfp-recent-list">
        {ticketIds.map((ticketId) => (
          <li key={ticketId}>
            <Link href={`/backoffice/rfp/${ticketId}`}>
              <span>Ticket {ticketId}</span>
            </Link>
          </li>
        ))}
      </ul>
    </section>
  );
};
