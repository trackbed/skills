import { quote } from "../quote.js";

export function invoiceLine(parcel) {
  return `Shipping: ${quote(parcel).total}`;
}
