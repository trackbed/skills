import { quote } from "../quote.js";

export function book(parcel) {
  return { bookingId: parcel.id, shipping: quote(parcel).total };
}
