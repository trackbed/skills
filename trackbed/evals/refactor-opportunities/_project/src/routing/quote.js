import { charge } from "./tariff.js";

export function quote(parcel) {
  return { id: parcel.id, total: charge(parcel.massKg) };
}
