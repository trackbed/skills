import { quote } from "../quote.js";

export function insuredTotal(parcel, declaredValue) {
  return declaredValue + quote(parcel).total;
}
