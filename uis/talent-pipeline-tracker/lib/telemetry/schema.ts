/**
 * Closed event catalogue and property allowlists from
 * docs/telemetry/event-schemas.json. Do not add keys or event names here
 * unless they exist in that file.
 */

export const TELEMETRY_SCHEMA_VERSION = "1.0.0";

export const TELEMETRY_EVENT_TYPES = [
  "inbound_order_created",
  "outbound_order_created",
  "stock_threshold_triggered",
  "direct_stock_edit_rejected",
  "supply_expiry_flagged",
  "user_login_succeeded",
  "user_login_failed",
  "session_expired",
  "user_logout_completed",
  "authorization_denied",
  "outbound_order_rejected",
  "api_request_completed",
  "page_load_completed",
  "frontend_error_uncaught",
  "page_viewed",
  "inventory_flow_abandoned",
] as const;

export type TelemetryEventType = (typeof TELEMETRY_EVENT_TYPES)[number];

export const EVENT_PROPERTY_ALLOWLIST: Record<
  TelemetryEventType,
  readonly string[]
> = {
  inbound_order_created: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "vendor_name",
    "inbound_order_id",
    "total_cost",
  ],
  outbound_order_created: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "department",
    "outbound_order_id",
    "consumption_reason",
  ],
  stock_threshold_triggered: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "minimum_stock",
    "triggering_outbound_order_id",
  ],
  direct_stock_edit_rejected: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "http_method",
    "route_template",
    "rejection_reason",
  ],
  supply_expiry_flagged: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "expiry_date",
    "days_until_expiry",
    "expiry_window_days",
  ],
  user_login_succeeded: ["auth_method", "role"],
  user_login_failed: ["failure_reason"],
  session_expired: ["expiry_source", "attempted_route"],
  user_logout_completed: ["logout_method"],
  authorization_denied: [
    "http_method",
    "route_template",
    "status_code",
    "denial_reason",
  ],
  outbound_order_rejected: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "available_quantity",
    "rejection_reason",
    "department",
  ],
  api_request_completed: [
    "http_method",
    "route_template",
    "status_code",
    "duration_ms",
    "outcome",
  ],
  page_load_completed: ["route", "duration_ms", "navigation_type"],
  frontend_error_uncaught: [
    "error_name",
    "sanitized_message",
    "route",
    "stack_hash",
  ],
  page_viewed: ["route", "referrer_route"],
  inventory_flow_abandoned: [
    "flow_name",
    "last_completed_step",
    "time_in_flow_ms",
    "clinic_id",
    "product_id",
  ],
};

export const EVENT_REQUIRED_PROPERTIES: Record<
  TelemetryEventType,
  readonly string[]
> = {
  inbound_order_created: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "vendor_name",
    "inbound_order_id",
    "total_cost",
  ],
  outbound_order_created: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "department",
    "outbound_order_id",
  ],
  stock_threshold_triggered: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "minimum_stock",
    "triggering_outbound_order_id",
  ],
  direct_stock_edit_rejected: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "http_method",
    "route_template",
    "rejection_reason",
  ],
  supply_expiry_flagged: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "expiry_date",
    "days_until_expiry",
    "expiry_window_days",
  ],
  user_login_succeeded: ["auth_method", "role"],
  user_login_failed: ["failure_reason"],
  session_expired: ["expiry_source", "attempted_route"],
  user_logout_completed: ["logout_method"],
  authorization_denied: [
    "http_method",
    "route_template",
    "status_code",
    "denial_reason",
  ],
  outbound_order_rejected: [
    "clinic_id",
    "country",
    "product_id",
    "product_category",
    "quantity",
    "available_quantity",
    "rejection_reason",
  ],
  api_request_completed: [
    "http_method",
    "route_template",
    "status_code",
    "duration_ms",
    "outcome",
  ],
  page_load_completed: ["route", "duration_ms", "navigation_type"],
  frontend_error_uncaught: [
    "error_name",
    "sanitized_message",
    "route",
    "stack_hash",
  ],
  page_viewed: ["route"],
  inventory_flow_abandoned: [
    "flow_name",
    "last_completed_step",
    "time_in_flow_ms",
  ],
};

export const isTelemetryEventType = (
  eventType: string,
): eventType is TelemetryEventType =>
  (TELEMETRY_EVENT_TYPES as readonly string[]).includes(eventType);
