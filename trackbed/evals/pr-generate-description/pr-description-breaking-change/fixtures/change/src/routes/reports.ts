import { Router } from "express";
import type { ReportStore } from "../store";

export function reportsRouter(store: ReportStore): Router {
  const router = Router();

  router.get("/v1/reports", async (request, response) => {
    const visible: string[] = response.locals.accountIds;
    const accountId = request.query.accountId;
    if (typeof accountId !== "string" || accountId === "") {
      response.status(400).json({ error: "accountId is required" });
      return;
    }
    const accountIds = visible.filter((id) => id === accountId);
    const createdAfter =
      typeof request.query.createdAfter === "string"
        ? request.query.createdAfter
        : undefined;
    const reports = await store.list({ accountIds, createdAfter });
    response.json({ reports });
  });

  return router;
}
