/** Health endpoint: GET /v1/health (public, no auth). */

import { request } from "./client";
import type { HealthResponse } from "./types";

/** Verify API + database connectivity. Useful for status indicators. */
export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>("GET", "/v1/health");
}
