import assert from "node:assert/strict";
import { acceptOrder } from "../src/channels/api.js";
import { importOrder } from "../src/channels/csv.js";
import { previewOrder } from "../src/channels/preview.js";
import { batchTotal } from "../src/routing/desks/batch.js";
import { book } from "../src/routing/desks/booking.js";
import { withinBudget } from "../src/routing/desks/budget.js";
import { insuredTotal } from "../src/routing/desks/insurance.js";
import { invoiceLine } from "../src/routing/desks/invoice.js";
import { priceNotice } from "../src/routing/desks/notice.js";
import { receipt } from "../src/routing/desks/receipt.js";
import { refundLimit } from "../src/routing/desks/refund.js";
import { quote } from "../src/routing/quote.js";
import { gramsToKilograms, kilogramsToGrams } from "../src/units/weight.js";

for (const channel of [acceptOrder, importOrder, previewOrder]) {
  assert.equal(channel({ destination: "island", massKg: 21 }).nextDay, false);
  assert.equal(channel({ destination: "island", massKg: 20 }).nextDay, true);
  assert.equal(channel({ destination: "city", massKg: 21 }).nextDay, true);
}
assert.equal(typeof quote({ id: "p1", massKg: 2 }).total, "number");
assert.equal(kilogramsToGrams(2), 2000);
assert.equal(gramsToKilograms(500), 0.5);
assert.equal(book({ id: "p", massKg: 2 }).bookingId, "p");
assert.equal(invoiceLine({ id: "p", massKg: 2 }).startsWith("Shipping:"), true);
assert.equal(withinBudget({ id: "p", massKg: 2 }, 1000), true);
assert.equal(receipt({ id: "p", massKg: 2 }).currency, "DKK");
assert.equal(refundLimit({ id: "p", massKg: 2 }, 1), 1);
assert.equal(insuredTotal({ id: "p", massKg: 2 }, 100) > 100, true);
assert.equal(priceNotice({ id: "p", massKg: 2 }).includes("Parcel p"), true);
assert.equal(batchTotal([]), 0);
