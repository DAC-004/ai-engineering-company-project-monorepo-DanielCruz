"use client";

import { useCallback, useState } from "react";

interface AsyncActionState {
  isSubmitting: boolean;
  error: string | null;
  success: string | null;
}

export function useAsyncAction() {
  const [state, setState] = useState<AsyncActionState>({
    isSubmitting: false,
    error: null,
    success: null,
  });

  const clearMessages = useCallback(() => {
    setState((current) => ({ ...current, error: null, success: null }));
  }, []);

  const run = useCallback(
    async <T,>(
      action: () => Promise<T>,
      successMessage = "Changes saved successfully.",
    ): Promise<T | null> => {
      setState({ isSubmitting: true, error: null, success: null });

      try {
        const result = await action();
        setState({
          isSubmitting: false,
          error: null,
          success: successMessage,
        });
        return result;
      } catch (error) {
        const message =
          error instanceof Error ? error.message : "Something went wrong.";
        setState({ isSubmitting: false, error: message, success: null });
        return null;
      }
    },
    [],
  );

  return {
    ...state,
    run,
    clearMessages,
  };
}
