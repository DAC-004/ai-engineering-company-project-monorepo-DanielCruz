interface SuccessMessageProps {
  message: string;
}

export function SuccessMessage({ message }: SuccessMessageProps) {
  return (
    <div
      className="rounded-xl border border-emerald-200 bg-emerald-50 px-5 py-4 text-base font-medium text-emerald-900"
      role="status"
    >
      {message}
    </div>
  );
}
