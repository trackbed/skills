import { isNextDayEligible } from "./eligibility.js";

export function importOrder(order) {
  return { reference: order.reference, nextDay: isNextDayEligible(order) };
}
