# Decision Document Content

The content file is everything the document says. The builder turns it into the page; you never write HTML. `assets/example/content.json` is a complete, invented example: read it beside this file.

## Reader first

The reader came to decide. Judge the content by whether each item can be decided from what is on its page.

- **Lead with the verdict.** `document.summary` opens with what the reader should conclude and do first, in two or three sentences. Someone who reads nothing else should leave with the right idea.
- **Titles are statements.** Write `Two members can be confirmed for the same studio and time`, never `Booking issue`. An item title states the problem or the question; an option name states the approach.
- **One idea per field.** `summary` says what is true, `impact` says why it matters, `reasoning` says why this option. Do not repeat one in another.
- **Plain words.** Explain a term from the source's own vocabulary, such as a label, a round name, or a score, the first time it appears. Wrap code and identifiers in backticks in sentences, captions, table cells, `status`, detail values, and the `source` of an evidence entry or of the document; that is the only markup the content takes. Ids, labels, and other short labels are plain text.
- **Fit the subject.** Every field marked optional is left out when the source has nothing for it. A plan needs no screenshots; a finding with one sensible fix has one option.

## What must come from the source

- **Ids.** `items[].id` is the source's own id (`PROD-001`, `W02B`, `Q3`). When the source gives none, number them `D-01`, `D-02` in source order. On a rebuild, an item keeps the id it had, a new item takes the next unused number, and a retired number is never used again.
- **Evidence.** Embed the captures, tables, and excerpts the source cites or the conversation produced, and quote text exactly as the source has it. A visual you make yourself follows the rules under [Visual aids](#visual-aids). Give every entry a `caption` saying what it shows and a `source` saying where it came from.
- **Claims.** Severity, counts, confidence, and status are the source's. Reword for clarity; never change what is claimed.
- **Nothing invented.** No evidence, estimate, or effort figure that the source or the user did not supply, and no option written to fill out a list or to make another look better. An option is real when the source names it, the user raised it, or it is a way you weighed and a careful person would too; when it is yours, label it as the next rule says. If only one approach is real, offer one option: the reader can still choose a different approach or no change. If nothing can be recommended, set `recommendation.option` to `null` and say in `reasoning` what would settle it.
- **Judgment is yours to give, and to label.** What an option gives and costs, and which one to recommend, often go beyond what the source says. Reason them from the source's evidence and state no number it does not give. Whenever a tradeoff or a recommendation is yours and not the source's, say so in the document: add a `document.sections` entry such as "What is the source's and what is judgment".
- **Limits are stated, not guessed.** `evidenceLimits` holds only what the source says was not tested, measured, or reproduced. `uncertainty` goes with the recommendation: when the recommendation is your judgment, so is what could make it wrong. A gap in the source that you notice yourself goes to the user in your closing message.

## Visual aids

A decision is quicker to make when the reader can see the thing. For every item, ask what they would need to see in order to decide, and for each such thing give them the first of these that fits. This is part of the work, not an extra: look for a visual before you settle for prose.

| The reader needs to see | Give them | Built from |
| --- | --- | --- |
| A screen, a page, or an output as it looked | `image`: the source's own capture | The file the source cites, or one beside it |
| How a few numbers compare, or how far one is past a limit | `chart` | Numbers the source states |
| The order things happen in | `steps` on the item | The source's account |
| A path that branches, how parts connect, or a before and an after | `image`: a diagram you draw | Steps, parts, and links the source states |
| Exact values to look up | `table` | The source |
| The wording itself | `excerpt` | The source |

- **Look before you draw.** Search the source, the folder it sits in, and any folder it names for captures and figures, and match each to its item by what the source says about it. The source's own picture beats one you make.
- **One claim each.** A visual shows one thing, and its `caption` says what that thing is. Two claims are two visuals.
- **Only what is stated.** A chart holds the source's numbers and no others. A diagram shows the steps, parts, and links the source or the conversation states, in the words they use. Never draw what you inferred, and never draw a number.
- **Mark what you made.** Set `"origin": "added"` on a capture you took and on a diagram you drew, and let `source` say what it was made from. The page then labels it "Made for this document", so nobody takes it for the source's evidence. A chart is labelled that way automatically.
- **No decoration.** When no visual would make an item quicker to decide, add none. One number belongs in a sentence, and so do two that are far apart, unless the point is where they fall against a limit. Do not show the same thing twice: when `steps` already tells a sequence, a diagram of that sequence adds nothing unless it sits beside the options' diagrams for comparison.

### Drawing a diagram

Copy `assets/diagram-template.svg` and replace its content, keeping its sizes and colours: red marks where it goes wrong, green the proposed path, grey everything else. Six to eight shapes is plenty; split a bigger picture in two. Write the file into a folder beside the content file, named as the page is with `.assets` in place of `.html`, and give its absolute path as `file` (a path that is not absolute starts at `--base-dir`). To compare options, draw today's picture and then the same picture once per option, and give each a `label`, so the reader can switch between them. Draw an option only as far as the source describes it; when that would be a single box, leave that option undrawn.

### Taking a capture

Take a new capture only when a browser tool is available and the page or screen is already there to open: a running app, or a file. Do not start, install, or change anything to get one. A capture taken now shows the current state, which may not be what the source saw, so say in its caption that it was taken for this document and when.

### Drawing a chart

A `chart` is horizontal bars on one scale that starts at zero, with each value printed at its bar. Use it for two to twelve values of the same kind. Add `limit` when the point is how far a value is past a threshold, and `emphasize` when one or two bars are the point and the others are context. Anything a bar chart cannot show honestly, such as values of different kinds, stays a `table`.

## Structure

```json
{
  "schemaVersion": 1,
  "document": { "id": "…", "title": "…", "summary": "…" },
  "items": [
    {
      "id": "…",
      "title": "…",
      "summary": "…",
      "recommendation": { "option": null, "summary": "…", "reasoning": "…" }
    }
  ]
}
```

A text field marked _text or list_ takes one string or a list of strings; a list reads as paragraphs, or as bullet points where noted. The builder rejects a field it does not know, so a typo is reported instead of dropped.

### `document`

| Field | Required | What it holds |
| --- | --- | --- |
| `id` | yes | 3 to 64 lowercase letters, digits, and hyphens. It identifies the document across rebuilds and names the place the browser keeps choices, so derive it from the subject (`checkout-review-2026-03`) and never change it for the same document. |
| `title` | yes | The document's name, as the reader would say it. |
| `summary` | yes | _Text or list._ The verdict and the first step. The first paragraph is set large. |
| `kicker` | no | A short line above the title, such as the kind of review and its scope. |
| `generated` | no | `YYYY-MM-DD`. Defaults to today. |
| `producer` | no | What produced the source, such as `trackbed:product:review`. |
| `itemNoun` | no | Singular and plural of what an item is: `["finding", "findings"]`. Defaults to `["decision", "decisions"]`. |
| `metrics` | no | At most four `{ "value", "label" }` counts the source states. |
| `startWith` | no | At most three items to read first: an item id, or `{ "item", "reason" }`. |
| `order` | no | A suggested order: groups of `{ "label", "title", "summary", "why", "items" }`, where `items` lists item ids and no item appears twice. Only when the source gives an order beyond its severity grouping, such as a fix order or waves, or the user asked for one. Otherwise point at the first items with `startWith`. |
| `sources` | no | `{ "label", "detail" }` for each report, plan, or conversation the document was built from. |
| `sections` | no | `{ "title", "paragraphs", "bullets" }` for what the reader needs about method and limits: what was covered, what was ruled out, what the evidence does not establish. |

### `items[]`

| Field | Required | What it holds |
| --- | --- | --- |
| `id` | yes | The source's id: letters, digits, dots, hyphens, underscores. |
| `title` | yes | The problem or the question, as a statement. |
| `summary` | yes | _Text or list._ What is true and how it shows, in two or three sentences. |
| `recommendation` | yes | `{ "option", "summary", "reasoning" }`. `option` is an option id, `"no-change"`, or `null`. `summary` is the recommendation in one sentence; `reasoning` (_text or list_) is why. |
| `labels` | no | At most four: a string, or `{ "text", "tone" }` with tone `critical`, `high`, `medium`, `low`, `good`, or `neutral`. Use the source's own words, such as its severity. |
| `status` | no | Where the item stands in the source (`Open · last verified in round 4`). This is never the reader's decision status. |
| `impact` | no | _Text or list._ Why it matters to the people affected. |
| `steps` | no | A list: the short sequence that shows the problem, when there is one. |
| `evidence` | no | See below. |
| `options` | no | Up to six; see below. |
| `noChange` | no | `true` (default) offers "No change". `{ "label", "description" }` words it for the subject, such as `Keep the 24-hour window`. `false` removes it only when doing nothing is not possible, such as a choice between two required migrations. A reader can decide to live with a known problem, so keep it on findings. |
| `uncertainty` | no | _Text or bullets._ What could make the recommendation wrong, and what would change it. |
| `evidenceLimits` | no | _Text or bullets._ What the evidence does not cover: what was not tested, measured, or reproduced. |
| `successCriteria` | no | _Text or bullets._ How to tell the chosen approach worked. |
| `details` | no | `{ "label", "value" }` facts the reader rarely needs, such as confidence or owner. |
| `source` | no | `{ "title", "location" }`: the item's title and place in the source, for tracing back. |

### `options[]`

| Field | Required | What it holds |
| --- | --- | --- |
| `id` | yes | Lowercase letters, digits, hyphens. Name the approach (`reserve-on-book`), never its position (`option-a`): the reader's choice is recorded against this id. `custom` and `no-change` are taken. |
| `name` | yes | The approach as a short phrase. |
| `summary` | one of these | _Text or list._ What choosing it means. |
| `benefits` | one of these | _Text or bullets._ What it gives. |
| `tradeoffs` | no | _Text or bullets._ What it costs or leaves unsolved, from the source or reasoned from it. Leave it out when you can name no real cost; never write one to fill the row. |

Two approaches are separate options when choosing between them matters to the reader. Variants of one approach, such as two ways to write the same fix, are one option.

The page always adds "A different approach", so the reader is never limited to the options written here.

### `evidence[]`

Every entry takes `type`, `caption` (required), and optional `label`, `source`, and `origin`. `origin` is `"source"` for what the source itself holds, which is the default, or `"added"` for what you made for the document; an added entry must have a `source`.

| `type` | Extra fields | Use it for |
| --- | --- | --- |
| `image` | `file` (required), `alt`, `focus` | A capture or figure. `file` is a path to a PNG, JPEG, GIF, WebP, AVIF, or SVG of at most 10 MB, relative to `--base-dir`; the builder embeds it. `label` names its tab when an item has several. `focus` (`"50% 20%"`) shows a cropped window on that point of a very tall capture; the full image still opens. `source` defaults to the path. |
| `table` | `rows` (required), `columns` | Measured or recorded values. Each row is a list of cells; the first cell is the row's heading. |
| `excerpt` | `text` (required) | Quoted code, output, or a passage, shown exactly as written. |
| `chart` | `rows` (required), `unit`, `emphasize`, `limit` | A few numbers compared as bars. `rows` holds two to twelve `[label, number]` pairs, each number zero or more. `unit` is a short suffix such as `s`, `ms`, or `%`; leave it out for a plain count and say in the `label` what is counted. `emphasize` lists the labels of the bars that are the point. `limit` is `{ "label", "value" }` for a threshold drawn across the bars. `source` is required: it says where the numbers are. |

## Identity and rebuilding

The builder gives every item a version computed from its `id`, `title`, `summary`, each option's `id`, `name`, `summary`, `benefits`, and `tradeoffs`, and the no-change wording. A recorded choice stays attached to an item while that version is unchanged.

- Changing evidence, the recommendation, labels, status, or the supporting notes keeps choices attached.
- Changing the statement or the options sends an earlier choice back to the reader marked **Needs review**, never as decided.
- Removing an item, or changing its id, drops its choice; the builder lists each one it dropped.

So when you rebuild, keep `document.id`, every item id, and every option id, and change wording in the versioned fields only when the meaning changed.
