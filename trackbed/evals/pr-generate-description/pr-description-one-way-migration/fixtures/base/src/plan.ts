export interface Account {
  id: string;
  plan_id: string | null;
  legacy_plan: string | null;
}

const LEGACY_PLAN_IDS: Record<string, string> = {
  basic: "plan_starter",
  plus: "plan_team",
  max: "plan_business",
};

export function currentPlan(account: Account): string {
  if (account.plan_id) return account.plan_id;
  const mapped = account.legacy_plan && LEGACY_PLAN_IDS[account.legacy_plan];
  if (mapped) return mapped;
  throw new Error(`Account ${account.id} has no plan`);
}
