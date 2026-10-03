interface ErrorStateProps {
  message: string;
  onRetry?: () => void;
}

export function ErrorState({ message, onRetry }: ErrorStateProps) {
  return (
    <div
      className="surface-card border-rose-200 bg-rose-50 px-6 py-5 text-rose-900"
      role="alert"
    >
      <p className="text-base font-semibold">Something went wrong</p>
      <p className="mt-2 text-base leading-7 text-rose-800">{message}</p>
      {onRetry ? (
        <button type="button" onClick={onRetry} className="btn-primary mt-4">
          Try again
        </button>
      ) : null}
    </div>
  );
}
