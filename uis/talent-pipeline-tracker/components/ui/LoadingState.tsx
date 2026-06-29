interface LoadingStateProps {
  message?: string;
}

export function LoadingState({
  message = "Loading...",
}: LoadingStateProps) {
  return (
    <div className="surface-card flex items-center justify-center px-6 py-16">
      <div className="flex items-center gap-4 text-base text-slate-600">
        <span
          className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-teal-600 border-t-transparent"
          aria-hidden="true"
        />
        <span>{message}</span>
      </div>
    </div>
  );
}
