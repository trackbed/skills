import { quote } from "../quote.js";

export function batchTotal(parcels) {
  return parcels.reduce((total, parcel) => total + quote(parcel).total, 0);
}
