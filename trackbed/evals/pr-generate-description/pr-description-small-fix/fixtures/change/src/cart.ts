export interface CartItem {
  sku: string;
  price: number;
  quantity: number;
}

export function cartTotal(items: CartItem[]): number {
  for (const item of items) {
    if (!Number.isInteger(item.quantity) || item.quantity < 0) {
      throw new RangeError(
        `Quantity for ${item.sku} must be a whole number of zero or more`,
      );
    }
  }
  return items.reduce((sum, item) => sum + item.price * item.quantity, 0);
}
