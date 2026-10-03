type SectionCardProps = {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
};

export function SectionCard({ title, subtitle, children }: SectionCardProps) {
  return (
    <section className="rounded-4xl border border-(--bo-line) bg-(--bo-surface) p-6 shadow-sm lg:p-7">
      <div className="mb-5">
        <h2 className="text-xl font-semibold text-(--bo-ink) lg:text-2xl">{title}</h2>
        {subtitle ? <p className="mt-2 text-sm leading-relaxed text-(--bo-muted)">{subtitle}</p> : null}
      </div>
      {children}
    </section>
  );
}
