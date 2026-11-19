import { isNextDayEligible } from "./eligibility.js";

export function acceptOrder(order) {
  return { reference: order.reference, nextDay: isNextDayEligible(order) };
}
