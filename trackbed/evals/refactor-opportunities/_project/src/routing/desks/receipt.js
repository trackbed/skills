import { quote } from "../quote.js";

export function receipt(parcel) {
  return { reference: parcel.id, amount: quote(parcel).total, currency: "DKK" };
}
