interface LoadingStateProps {
  message?: string;
}

export function LoadingState({
  message = "Loading...",
}: LoadingStateProps) {
  return (
    <div className="flex items-center justify-center rounded-xl border border-slate-200 bg-white px-6 py-12 text-slate-600">
      <div className="flex items-center gap-3">
        <span className="inline-block h-5 w-5 animate-spin rounded-full border-2 border-teal-600 border-t-transparent" />
        <span>{message}</span>
      </div>
    </div>
  );
}
