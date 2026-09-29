"use client";

import { useParams } from "next/navigation";

import { RfpTicketPanel } from "@/components/rfp/RfpTicketPanel";

export default function RfpTicketPage() {
  const params = useParams<{ ticketId: string }>();
  const ticketId = params.ticketId;

  return (
    <section className="home-panel">
      <p className="eyebrow">RFP intake</p>
      <h1>Ticket</h1>
      {ticketId ? <RfpTicketPanel ticketId={ticketId} /> : <p>Ticket id is missing.</p>}
    </section>
  );
}
