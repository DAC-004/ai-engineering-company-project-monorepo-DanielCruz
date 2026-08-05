type MetricCardProps = {
  label: string;
  value: string | number;
  detail?: string;
};

export function MetricCard({ label, value, detail }: MetricCardProps) {
  return (
    <article className="rounded-3xl border border-(--bo-line) bg-(--bo-surface) p-5 shadow-sm">
      <p className="text-sm font-semibold uppercase tracking-[0.16em] text-(--bo-muted)">
        {label}
      </p>
      <p className="mt-3 text-3xl font-bold text-(--bo-ink)">{value}</p>
      {detail ? <p className="mt-2 text-sm leading-relaxed text-(--bo-muted)">{detail}</p> : null}
    </article>
  );
}
