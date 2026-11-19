const restrictedDestinations = new Set(["island", "skerry"]);

export function isNextDayEligible(order) {
  return !(restrictedDestinations.has(order.destination) && order.massKg > 20);
}
