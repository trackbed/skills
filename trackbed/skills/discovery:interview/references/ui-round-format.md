# Round File Format

One round file is one page of questions for `--ui` mode. You write it; the helper checks it and builds the page. `assets/ui-round-example.json` is a complete round to read beside this.

The page is drawn from the file alone, so the file is where the interview's quality lives: the right control for each question, real alternatives, and a figure wherever seeing is quicker than reading.

## The round

```json
{
  "format": "trackbed-interview-round",
  "schemaVersion": 1,
  "session": {
    "id": "email-2fa-a8192ba4817a6e28",
    "title": "Email-based 2FA for login",
    "topic": "Software Feature"
  },
  "number": 2,
  "title": "Where the code step lives, and what stays out",
  "synthesis": ["What you took from the answers so far, in a sentence or two."],
  "progress": {
    "label": "Coverage",
    "target": 80,
    "entries": [{ "label": "Security", "value": 60 }]
  },
  "questions": []
}
```

| Field | Meaning |
| --- | --- |
| `session.id` | A fresh ID for each interview, reused for all its rounds. Lowercase letters, digits, and hyphens. |
| `session.title` | What the interview is about. `session.topic` is the topic type and may be left out. |
| `number` | The round's number, counting from 1. |
| `title` | What this round settles, as a headline. |
| `synthesis` | One to four short paragraphs: the between-round synthesis. In round 1 it holds the Step 1 working hypothesis instead, as assumptions for the user to correct. |
| `progress` | The profile's progress display. Leave it out while there is nothing to show, as in round 1 of a coverage profile; a decision tree can be shown from the first round. |
| `questions` | One to eight questions. Keep to the round size of the active profile. |

Text fields take `` `code` `` and `**bold**` and nothing else. Write plain text: the helper escapes `<`, `>`, and `&`, so an HTML entity would be shown as typed. Every id is lowercase letters, digits, and hyphens.

**Progress** has a `label` and `entries`. An entry with a `value` from 0 to 100 is drawn as a meter, for coverage dimensions and confidence dimensions; `target` marks the profile's threshold on every meter. An entry with a `state` of `resolved`, `active`, or `open` is drawn as a node of the decision tree, indented by `depth` (0 to 4). Either kind takes a short `note`, such as the answer a resolved branch settled on.

## A question

Every question has these:

| Field | Meaning |
| --- | --- |
| `id` | Its own id within the round. |
| `kind` | The control: see the next section. |
| `title` | The question, as the user reads it. |
| `why` | Why this matters: one or two sentences on what it decides and what goes wrong if it is decided badly. Required. |
| `dimension` | The coverage or confidence dimension it belongs to, shown as a label. Use the wording of its `progress` entry when it has one. Optional. |
| `figure` | A visual aid for the whole question. Optional. |
| `recommendation` | `{ "pick": …, "reason": "…" }`. Required on `choice`, `rank`, `scale`, `allocate`, and `matrix`; not taken on `confirm` and `text`. |

`recommendation.pick` is a complete answer in the question's own shape, shown beside the control and never selected for the user. Use `"pick": null` with a `reason` when you have no preference: say what the choice depends on.

## Choose the control that fits the question

A list of options is one way to ask. Pick the kind by what the answer really is:

| The answer is… | Kind | Kind-specific fields |
| --- | --- | --- |
| One of a few real alternatives, or several of them | `choice` | `options` (2 to 6), `multiple`, `other` |
| An order of importance | `rank` | `items` (2 to 8) |
| A point between two poles | `scale` | `low`, `high`, `steps` (3 to 7, default 5) |
| A budget split across competing things | `allocate` | `items` (2 to 8), `total` (default 100), `unit`, `step` |
| The same small decision for each of several things | `matrix` | `rows` (1 to 10), `columns` (2 to 5) |
| Yes or no to something you already found | `confirm` | `statement`, `source` |
| Something only they can put into words | `text` | `placeholder`, `long` |

- **`choice`**: each option has an `id`, a `label`, and may have a `description`, up to four `gives`, up to four `costs`, and its own `figure`. Every option is a choice someone would really make. The page adds "Something else" with a text field unless `other` is `false`. `pick` is an option id, or a list of ids when `multiple` is `true`.
- **`rank`**: for forced prioritization across more than two things. Give the `items` in a neutral order. `pick` is every item id in your recommended order.
- **`scale`**: for a tradeoff with two honest ends, such as speed against thoroughness. `low` and `high` name the ends. `pick` is a stop number, 1 being `low`.
- **`allocate`**: for "where should the effort go" when ranking would hide how much more one thing matters. Each amount must be a multiple of `step`, and the amounts must add up to `total`. The default step is 5 when the total is at least 50 and divisible by 5, and 1 otherwise. `pick` is an object of item id to amount.
- **`matrix`**: for sorting many things into the same few buckets in one question, such as scope (`This pass`, `Later`, `Never`), ownership, or risk tolerance. Use it for non-goals. `pick` is an object of row id to column id.
- **`confirm`**: for the codebase-as-answer-source rule and the restatement challenge. `statement` is what you inferred; `source` is where you found it, as one line of text that may name several places. The user confirms or says what is right.
- **`text`**: for a why chain, a past failure, or anything a list of options would flatten. Set `long` to `true` when you expect a paragraph.

`rank`, `allocate`, and `matrix` entries have an `id`, a `label`, and an optional `description`. Every question also lets the user mark "Not sure" and add a note, so never spend an option on those.

## Figures

A question or choice option accepts either one `figure` or an ordered `figures` array of one to four figures. Place them in the order that helps the reader decide. Every kind accepts a `caption`. Charts and screenshots also require a `title` and a `source` identifying the capture, dataset, or scenario assumptions.

| `kind` | Fields | Use it for |
| --- | --- | --- |
| `chart` | `title`, `source`, `unit`, `labels`, `series` | Compare trends or sensitivity across ordered, equally spaced observations. Move the inspection slider to compare all series at one observation, or expand the full data table. |
| `screenshot` | `title`, `source`, `file`, `alt`, optional `callouts` | Show the product as observed. The reader can enlarge the capture and inspect the numbered details. |
| `sketch` | `svg`, `alt` | What an option would look like: a wireframe, a layout, a data flow. |
| `steps` | `steps` (2 to 8) | A sequence: today's flow, or the flow an option proposes. |
| `bars` | `bars` (2 to 8 of `label` and finite, nonnegative `value`), `unit` | A few numbers compared. |
| `code` | `code`, `language` | A snippet from the repository, or the shape an option would give an API. |
| `table` | `columns` (2 to 6), `rows` (1 to 10) | Options set against criteria. |

- **Show the difference.** When two options differ in something visible, give each a `sketch` drawn to the same size, so the user compares pictures and not paragraphs.
- **A sketch** is one complete `<svg>` element with a `viewBox` and `xmlns="http://www.w3.org/2000/svg"`, drawn from `assets/ui-sketch-template.svg`. It is shown as a picture, so it holds no script, links, images, or fonts from elsewhere. Its `alt` says what it shows and is what the page reads out; a `<title>` inside the SVG is optional.
- **A figure shows what you know.** Numbers come from the codebase, the research pass, or the user. When a number is your estimate, say so in the caption; never invent a measurement.

### Screenshot and chart examples

Use a PNG, JPEG, or WebP file placed directly beside the round JSON (up to 10 MB per file and 32 MB of encoded images per round). The capture is embedded in the built page. Keep the original beside the JSON for pasted-answer validation. Each optional pin uses integer percentages from the left and top edges and a short explanation. Crop to the relevant area and omit unrelated personal information. Identify live product captures, mockups, and proposed changes accurately.

For a line chart, supply 2–24 ordered x labels and 1–4 named series with one finite value per label, all in the same unit. Use a bar comparison or table for unordered alternatives. The following example pairs an actual capture you supply with an explicitly modeled scenario:

```json
"figures": [
  {
    "kind": "screenshot", "file": "verification.png", "title": "Where users can request a new code",
    "alt": "Verification form with a resend action below the primary button",
    "source": "Local sign-in prototype · verification step",
    "callouts": [{"x": 44, "y": 81, "text": "Resending leaves the user on this step."}]
  },
  {
    "kind": "chart", "title": "How often would someone need a code?", "unit": "Prompts",
    "labels": ["Week 1", "Week 2", "Week 3", "Week 4"],
    "series": [
      {"label": "Every login", "values": [5, 10, 15, 20]},
      {"label": "Remember device", "values": [1, 1, 1, 1]}
    ],
    "source": "Illustrative cumulative model · five logins per week on one device.",
    "caption": "The gap depends on how often people return to the same device."
  }
]
```

## What the helper checks

The helper refuses a round with an unknown field, a missing `why`, a missing recommendation, a recommendation that is not a possible answer, ids used twice, or a sketch that is not inert. It prints one line per problem, each naming the field. Fix the file; the checks are the contract with the page.
