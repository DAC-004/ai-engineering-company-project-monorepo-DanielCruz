import { useEffect, useRef } from "react";

import { track } from "@/src/services/telemetry";

export type InventoryFlowName = "inbound_order" | "outbound_order";

export type InventoryFlowStep =
  | "form_opened"
  | "product_selected"
  | "quantity_entered"
  | "clinic_selected"
  | "ready_to_submit";

type InventoryFlowState = {
  flowName: InventoryFlowName;
  lastCompletedStep: InventoryFlowStep;
  startedAt: number;
  submitted: boolean;
  clinicId?: number;
  productId?: number;
};

const resolveFlowState = (
  flowName: InventoryFlowName,
  state: {
    productId: string;
    quantity: string;
    clinicId: string;
    readyToSubmit: boolean;
    submitted: boolean;
  },
  startedAt: number,
): InventoryFlowState => {
  const next: InventoryFlowState = {
    flowName,
    lastCompletedStep: "form_opened",
    startedAt,
    submitted: state.submitted,
  };

  if (state.productId) {
    const productId = Number(state.productId);
    if (!Number.isNaN(productId)) {
      next.productId = productId;
      next.lastCompletedStep = "product_selected";
    }
  }
  if (state.quantity && Number(state.quantity) > 0) {
    next.lastCompletedStep = "quantity_entered";
  }
  if (state.clinicId) {
    const clinicId = Number(state.clinicId);
    if (!Number.isNaN(clinicId)) {
      next.clinicId = clinicId;
      next.lastCompletedStep = "clinic_selected";
    }
  }
  if (state.readyToSubmit) {
    next.lastCompletedStep = "ready_to_submit";
  }
  return next;
};

export const useInventoryFlowTelemetry = (
  flowName: InventoryFlowName,
  state: {
    productId: string;
    quantity: string;
    clinicId: string;
    readyToSubmit: boolean;
    submitted: boolean;
  },
): void => {
  const { productId, quantity, clinicId, readyToSubmit, submitted } = state;
  const flowRef = useRef<InventoryFlowState>({
    flowName,
    lastCompletedStep: "form_opened",
    startedAt: 0,
    submitted: false,
  });

  useEffect(() => {
    if (flowRef.current.startedAt === 0) {
      flowRef.current.startedAt = Date.now();
    }
    flowRef.current = resolveFlowState(
      flowName,
      { productId, quantity, clinicId, readyToSubmit, submitted },
      flowRef.current.startedAt,
    );
  }, [flowName, productId, quantity, clinicId, readyToSubmit, submitted]);

  useEffect(() => {
    let emitted = false;
    const emitAbandoned = () => {
      const current = flowRef.current;
      if (current.submitted || emitted) {
        return;
      }
      emitted = true;
      const properties: Record<string, unknown> = {
        flow_name: current.flowName,
        last_completed_step: current.lastCompletedStep,
        time_in_flow_ms: Math.max(0, Date.now() - current.startedAt),
      };
      if (current.clinicId) {
        properties.clinic_id = current.clinicId;
      }
      if (current.productId) {
        properties.product_id = current.productId;
      }
      track("inventory_flow_abandoned", properties);
    };

    const onHidden = () => {
      if (document.visibilityState === "hidden") {
        emitAbandoned();
      }
    };

    document.addEventListener("visibilitychange", onHidden);
    return () => {
      document.removeEventListener("visibilitychange", onHidden);
      emitAbandoned();
    };
  }, []);
};
