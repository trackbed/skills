export function acceptOrder(order) {
  const nextDay = !(order.destination === "island" && order.massKg > 20);
  return { reference: order.reference, nextDay };
}
