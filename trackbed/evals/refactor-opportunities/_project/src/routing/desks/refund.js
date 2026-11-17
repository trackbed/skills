import { quote } from "../quote.js";

export function refundLimit(parcel, paid) {
  return Math.min(paid, quote(parcel).total);
}
