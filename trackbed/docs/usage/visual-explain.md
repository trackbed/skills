# visual:explain

Use it when a picture explains better than prose: an architecture overview, flowchart, sequence diagram, schema, state machine, timeline, dashboard, or data table. It writes one HTML page outside your repository and opens it in your browser. With `--onboarding` it explores the codebase and builds a guide for newcomers. To explain a branch or Pull Request, use `trackbed:pr:walkthrough`.

## Arguments

| Argument | Meaning |
| --- | --- |
| `[topic or description]` | What to explain or draw, in your own words: a system, a code change, a plan, or a set of data. |

## Options

| Option | Effect |
| --- | --- |
| `--onboarding [focus-area or audience]` | Build an onboarding guide to the codebase instead of a single diagram. Add a focus area, such as `frontend` or `auth`, to limit it to that subsystem, or an audience, such as `designer`, to adjust the technical depth. |

## Examples

```text
# Draw how one part of the system works
/trackbed:visual:explain how a request flows through the auth middleware

# Show a comparison as a table page
/trackbed:visual:explain compare our three caching options in a table

# Build an onboarding guide for the whole codebase
/trackbed:visual:explain --onboarding

# Build an onboarding guide for one area
/trackbed:visual:explain --onboarding frontend
```

## What you get

- One HTML file in `~/.trackbed/diagrams/`, named after its content, such as `pipeline-flow.html`. A later run that uses the same name overwrites it.
- With `--onboarding`, `~/.trackbed/diagrams/onboarding-{project-name}.html`: a project overview, architecture and domain diagrams, the main flows, setup steps, conventions, and a map of key files.
- The page opened in your default browser, and the file path in the reply. Where no browser can open, you get the path only.

The page is a single file with light and dark themes. Its fonts and diagram libraries load from the network. When the `surf` CLI is installed, the skill may add generated illustrations, and each one is a paid Google Gemini API call.

The agent also uses this skill on its own when it is about to print a table with at least four rows and three columns. It then writes the page and gives you the path without opening a browser. `trackbed:workflow:cleanup-artifacts` can clear the diagrams folder, which all your projects share.
