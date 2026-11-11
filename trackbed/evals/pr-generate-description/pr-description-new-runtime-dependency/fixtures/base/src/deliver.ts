import { logger } from "./logger";

export interface WebhookEvent {
  id: string;
  url: string;
  payload: unknown;
}

export async function deliver(event: WebhookEvent): Promise<void> {
  const response = await fetch(event.url, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(event.payload),
  });
  if (!response.ok) {
    logger.warn(
      { id: event.id, status: response.status },
      "webhook delivery failed",
    );
    throw new Error(`Webhook ${event.id} failed with ${response.status}`);
  }
}
