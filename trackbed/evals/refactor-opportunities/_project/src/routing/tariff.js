export const baseRate = 10;
export function charge(massKg) {
  return baseRate + massKg * 2;
}
