# product:review

Use it to review a running application as a whole (experimental). It opens the app in a browser, walks its main flows one step deep, and reports problems with navigation, discoverability, onboarding, consistency, dead ends, friction, trust, and copy. It does not change your code, and in the app it never triggers destructive or irreversible actions such as delete, pay, or send. To review the changes on a branch, use `trackbed:pr:product-review`; to audit a spec before it is built, use `trackbed:siw:spec-audit` with `--product`.

## Before you run it

- The application is running and reachable.
- A browser tool that `trackbed:browse` supports is connected: [Claude in Chrome](../mcp-servers.md#claude-in-chrome), [Chrome DevTools](../mcp-servers.md#chrome-devtools), or [Playwright](../mcp-servers.md#playwright).
- If the app needs a login, sign in in that browser first.

## Arguments

| Argument | Meaning |
| --- | --- |
| `<url\|auto>` | Required. The `http://` or `https://` address to review, or `auto` to find a running local dev server. With several servers running, the skill asks which one. |

## Options

| Option | Effect |
| --- | --- |
| `--flows <flow1,flow2,...>` | Review only these flows, as a comma-separated list such as `onboarding,settings,billing`. Without it, the skill picks 5 to 8 key flows from the navigation. |
| `--focus <dimension>` | Emphasize one dimension: `navigation` (or `ia`), `discoverability`, `onboarding`, `consistency`, `dead-ends`, `friction`, `trust-safety`, or `copy`. The others are still checked. |
| `--inline` | Reply with the report in the conversation and write no file. Cannot be combined with `--visual`. |
| `--visual` | Also write `PRODUCT_AUDIT_OVERVIEW.html`, an interactive page of the same report. See [Visual Reports](../visual-reports.md). |

## Examples

```text
# Review the app on the local dev server the skill finds
/trackbed:product:review auto

# Review two flows with extra attention to trust and safety
/trackbed:product:review http://localhost:4200 --flows checkout,payment --focus trust-safety

# Review a staging site and reply in the conversation
/trackbed:product:review https://staging.example.com --inline
```

## What you get

- `PRODUCT_AUDIT_OVERVIEW.md` in the project root: a summary, the flows reviewed, findings numbered from `PROD-001` and grouped as Critical, Important, and Suggestion, patterns across flows, strengths, and recommended actions ordered by effort.
- When an earlier `PRODUCT_AUDIT_OVERVIEW.md` exists, findings it already reported are listed separately and the ones that are gone are marked resolved. Runs with `--inline` do not feed this comparison.
- A closing message with the number of flows reviewed and the count of critical, important, and suggestion findings.

The report is a working file. Do not commit it; `trackbed:workflow:cleanup-artifacts` removes it.
