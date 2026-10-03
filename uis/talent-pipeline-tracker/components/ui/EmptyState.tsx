interface EmptyStateProps {
  title: string;
  description?: string;
}

export function EmptyState({ title, description }: EmptyStateProps) {
  return (
    <div className="surface-card border-dashed px-6 py-12 text-center md:px-8 md:py-16">
      <p className="text-lg font-semibold text-slate-900 md:text-xl">{title}</p>
      {description ? (
        <p className="mx-auto mt-3 max-w-xl text-base leading-7 text-slate-600">
          {description}
        </p>
      ) : null}
    </div>
  );
}
