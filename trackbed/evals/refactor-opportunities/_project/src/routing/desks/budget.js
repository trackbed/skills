import { quote } from "../quote.js";

export function withinBudget(parcel, budget) {
  return quote(parcel).total <= budget;
}
