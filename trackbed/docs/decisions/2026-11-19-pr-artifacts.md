# Upload Documents Written While Building a Change as Pull Request Artifacts

- Status: PROPOSED
- Date: 2026-11-19
- Deciders: repository maintainer (design choices made during the implementation request)

## Context

Workflows in this plugin write documents while a change is built: a plan, a QA report, a walkthrough page, review reports. They stay on the author's machine, and `trackbed:workflow:cleanup-artifacts` deletes most of them. A reviewer sees one only when its content is pasted into the description.

GitHub issue artifacts, in public preview since 2026-10-28, attach text documents to an issue: Markdown or plain text, and HTML pages that the reader can preview. `POST /repos/{owner}/{repo}/issues/{issue_number}/artifacts` creates one from a `type`, a `name`, and a `body`.

Checked against this repository on 2026-11-19:

- The endpoint treats a Pull Request number like an issue number. Listing returned `200` with an empty list, and an empty create request returned `422 name is required`, the same answer as for an issue.
- GitHub's reference for the endpoint describes only issues.
- `gh issue artifact`, added in GitHub CLI 2.103, refuses a Pull Request number before it sends a request.
- A renamed repository's old name answers the create request with `307`, which `gh api` does not follow.

UNVERIFIED: creating an artifact on a Pull Request succeeds. The checks above stopped at validation so that nothing was published. Source needed: the first run of `trackbed:pr:create` that uploads a document.

An artifact is as public as its Pull Request. Review reports can describe weaknesses that are not fixed yet, and workspace notes directories hold files the user pasted in.

## Decision

- `trackbed:pr:create` accepts `--artifact <file[#name]>`, repeatable, for a Markdown, text, or HTML file, and `--no-artifacts`. An invalid `--artifact` file stops the run before a rebase or commit.
- A direct invocation collects documents written while building the change unless `--no-artifacts` is set. It looks only at what the session wrote or was told about, at report, plan, and page files trackbed workflows left in the worktree, and at diagram and decision pages the session generated. The two delegated `--ship` workflows pass `--no-artifacts` to preserve their publication grant.
- A document qualifies only when it is about this change, a reviewer learns from it, it is still true, and reviewers do not already have it. Working state, user-supplied input, documents intended for the PR diff, superseded plans, and reports with a finding that is neither fixed nor accepted do not qualify. Git-visible local-only documents block the include-all commit. A manual run can stash and exclude them.
- Artifacts are for what a reviewer looks at or decides from. Documents are staged in this order: prototypes and pages that explain the change, decision records and decision pages, then the plan, specification, or research the change was built from. Review output comes last and is limited to one QA, review, or audit report that adds what the diff and description lack. A report whose findings are all fixed is not uploaded.
- Archived review reports under any `.context/<workflow>/reviews/` directory are never collected automatically. The helper enforces this; `--artifact` still accepts one.
- Screenshots and videos are not artifacts, because the API takes text. They stay attachments in the description, per [the screenshot decision](2026-11-18-pr-screenshot-evidence.md).
- The agent reads each automatic candidate before staging it and skips any with a credential, personal or customer data, an internal address, or a weakness the Pull Request does not fix. A document that describes a security weakness or copies text from a private source requires a confirmed private or internal destination. The helper checks the repository in the verified Pull Request URL. Auto mode skips the preview. `--manual` lists the documents in the confirmation preview.
- One plugin-level helper, `scripts/pr-artifacts.py`, owns staging, validation, and upload. It refuses binary, empty, oversized, and repeated documents, files the workflow would commit, and names or body text matching its credential patterns. An explicit source inside the checkout must be ignored or committed without local changes. It reads each staged document once at upload and scans the name and body before sending them. It shares its run-directory code with `scripts/pr-evidence.py` through `scripts/lib/pr_staging.py`. Documents are staged under `.trackbed/pr-artifacts/`, which Git's local exclude file hides.
- Upload runs once, after the created Pull Request is proven, through `gh api` and the repository named in the Pull Request's URL. An upload failure leaves the Pull Request in place. The helper stops when a response applies to every document, such as a missing API or permission. It binds a run to one Pull Request and records each attempt before sending it. A later invocation skips documents whose outcomes are unconfirmed.
- The description stays unchanged. The closing message includes any confirmed artifact links returned by the API.

## Consequences

- A successful artifact response gives reviewers a link to the document. Pull Request display and manual upload controls still need verification.
- The feature depends on a preview API and on behavior GitHub has not documented for Pull Requests. If GitHub refuses, the Pull Request remains open and the closing message names the available local copies.
- Automatic runs publish documents no person previewed. Safety rests on the agent's check and the credential scan.
- `trackbed:linear:issue-to-pr --ship` deletes its disposable workflow files before it creates the Pull Request. Every workflow's review archive stays local, such as `.context/code-plan-to-pr/reviews/` and `.context/pr-review-convergence/reviews/`. Direct `trackbed:pr:create` invocations can still collect eligible archived plans.
- The limits of 10 documents and 1 MB each are this helper's own; GitHub documents none.

## Alternatives Considered

### Call `gh issue artifact create`

Rejected because the command refuses Pull Requests and needs GitHub CLI 2.103 or later. `gh api` works with the versions this plugin already supports.

### Paste or link the documents in the description

Rejected because a long plan buries the summary a reviewer reads first, and a local file cannot be linked.

### Upload every registered workflow output

Rejected because the cleanup registry also lists drafts, run state, and reports that describe unfixed weaknesses, and it belongs to another skill.

### Upload every qualifying review report

Rejected because one convergence run leaves four or more reports, which would outnumber the prototypes, explanations, and decision records a reviewer opens.

### Preview documents before upload in auto mode

Rejected because it would make automatic runs interactive, as the screenshot decision also concluded.

### Stage review reports before `trackbed:linear:issue-to-pr` deletes them

Deferred. It would widen what `--ship` publishes, so it needs its own decision.
