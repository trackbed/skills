import { quote } from "../quote.js";

export function priceNotice(parcel) {
  return `Parcel ${parcel.id} costs ${quote(parcel).total} DKK`;
}
