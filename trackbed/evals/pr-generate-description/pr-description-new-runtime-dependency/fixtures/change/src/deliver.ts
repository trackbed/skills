import pRetry, { AbortError } from "p-retry";
import { logger } from "./logger";

export interface WebhookEvent {
  id: string;
  url: string;
  payload: unknown;
}

const RETRIES = 3;

async function attempt(event: WebhookEvent): Promise<void> {
  const response = await fetch(event.url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(event.payload),
  });
  if (response.ok) return;
  const error = new Error(
    `Webhook ${event.id} failed with ${response.status}`,
  );
  // The receiver rejected the event; sending it again will not help.
  if (response.status < 500) throw new AbortError(error);
  throw error;
}

export async function deliver(event: WebhookEvent): Promise<void> {
  await pRetry(() => attempt(event), {
    retries: RETRIES,
    onFailedAttempt: (error) => {
      logger.warn(
        { id: event.id, attempt: error.attemptNumber },
        "webhook delivery failed",
      );
    },
  });
}
