"use client";

import Link from "next/link";
import { useEffect, useState } from "react";

import { connectRfpNotifications, type RfpArrival } from "@/lib/rfpNotifications";

/**
 * One connection per browser tab. A replay and a later live frame for the
 * same ticket_id stay one row. This panel does not refetch inventory,
 * profile, or the per-ticket poll.
 */
export const RfpArrivalNotifications = () => {
  const [arrivals, setArrivals] = useState<RfpArrival[]>([]);
  const [replayGap, setReplayGap] = useState(false);

  useEffect(() => {
    const connection = connectRfpNotifications({
      onArrival: (arrival) => {
        setArrivals((current) => {
          if (current.some((item) => item.ticketId === arrival.ticketId)) {
            return current;
          }
          return [...current, arrival];
        });
      },
      onReplayGap: () => {
        setReplayGap(true);
      },
      onEstablished: () => undefined,
    });
    return () => {
      connection.stop();
    };
  }, []);

  return (
    <section className="rfp-arrival-panel" aria-live="polite">
      <p className="eyebrow">Revenue Cycle</p>
      <h2>New RFP tickets</h2>
      <p className="rfp-arrival-panel__note">
        Arrivals from the live stream. This list is separate from medical supplies and from a
        ticket page that is already open.
      </p>
      {replayGap ? (
        <p className="rfp-arrival-panel__gap" role="status">
          Tickets outside the current buffer were not restored.
        </p>
      ) : null}
      {arrivals.length === 0 ? (
        <p className="rfp-arrival-panel__empty">No new RFP tickets on this connection.</p>
      ) : (
        <ul className="rfp-arrival-list">
          {arrivals.map((arrival) => (
            <li key={arrival.ticketId}>
              <Link href={`/backoffice/rfp/${arrival.ticketId}`}>
                <span>Ticket {arrival.ticketId}</span>
                <span>RFP {arrival.rfpId}</span>
                <span>{arrival.status}</span>
                <span>{arrival.createdAt}</span>
              </Link>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
};
