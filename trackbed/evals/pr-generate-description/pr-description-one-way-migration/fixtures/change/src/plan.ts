export interface Account {
  id: string;
  plan_id: string | null;
}

export function currentPlan(account: Account): string {
  if (account.plan_id) return account.plan_id;
  throw new Error(`Account ${account.id} has no plan`);
}
