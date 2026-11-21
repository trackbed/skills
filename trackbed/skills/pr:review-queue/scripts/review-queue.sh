#!/usr/bin/env bash
#
# Print a JSON snapshot of the pull requests waiting on your review.
#
# Usage: review-queue.sh [--repo OWNER/NAME | --all-repos] [--since ISO-8601] [OWNER/NAME#NUMBER ...]
#   --repo       limit every search to this repository
#   --all-repos  search every repository the token can read
#   (neither)    limit every search to the current directory's GitHub repository
#   --since      also include PRs you reviewed that changed since then, and PRs
#                that requested you and closed since then (merged without your
#                review)
#   refs         PRs to re-query by number, such as every PR in the previous
#                report, whatever their repository
#
# Prints {checkedAt, me, prs: [...]} with one summarised object per PR, and
# warnings on stderr. Each PR carries how long it has waited on you, an estimate
# of whether it is ready for review, its linked issue, and the command that
# starts a review of it. Exits 2 on a usage error, including no --repo or
# --all-repos outside a GitHub repository, and nonzero when a search fails; an
# unreadable ref, an unlistable set of workflow runs, or unreadable required
# checks only warns. Needs an
# authenticated gh and jq. Runs under the Bash 3.2 that macOS ships, so guard
# empty-array expansions under set -u and do not use mapfile.

set -euo pipefail

usage() {
  echo "Usage: review-queue.sh [--repo OWNER/NAME | --all-repos] [--since ISO-8601] [OWNER/NAME#NUMBER ...]"
}

usage_error() {
  echo "review-queue.sh: $1" >&2
  usage >&2
  exit 2
}

repo=""
all_repos=false
since=""
refs=()
while [ $# -gt 0 ]; do
  case "$1" in
    --repo)
      [ $# -ge 2 ] || usage_error "--repo requires OWNER/NAME"
      repo=$2
      shift 2
      ;;
    --all-repos)
      all_repos=true
      shift
      ;;
    --since)
      [ $# -ge 2 ] || usage_error "--since requires an ISO-8601 date or time"
      since=$2
      shift 2
      ;;
    -h | --help)
      usage
      exit 0
      ;;
    -*) usage_error "unknown option: $1" ;;
    *)
      refs+=("$1")
      shift
      ;;
  esac
done

# Validate every value before it reaches a search query or a GraphQL variable.
slug_re='[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+'
repo_re="^$slug_re\$"
ref_re="^$slug_re#[0-9]+\$"
since_re='^[0-9]{4}-[0-9]{2}-[0-9]{2}(T[0-9]{2}:[0-9]{2}(:[0-9]{2})?(Z|[+-][0-9]{2}:[0-9]{2})?)?$'
if [ -n "$repo" ] && [ "$all_repos" = true ]; then
  usage_error "--repo and --all-repos cannot be combined"
fi
if [ -n "$repo" ] && ! [[ $repo =~ $repo_re ]]; then
  usage_error "--repo must be OWNER/NAME, got: $repo"
fi
if [ -n "$since" ] && ! [[ $since =~ $since_re ]]; then
  usage_error "--since must be an ISO-8601 date or time, got: $since"
fi
for ref in ${refs[@]+"${refs[@]}"}; do
  [[ $ref =~ $ref_re ]] || usage_error "a PR must be OWNER/NAME#NUMBER, got: $ref"
done

FRAGMENT='
fragment PR on PullRequest {
  number title url body isDraft state createdAt mergedAt mergedBy { login }
  repository { nameWithOwner defaultBranchRef { name } }
  author { login }
  baseRefName headRefName headRefOid additions deletions changedFiles
  baseRef {
    associatedPullRequests(states: OPEN, first: 10) { nodes { number url isDraft headRepository { nameWithOwner } } }
    refUpdateRule { pattern } rules(first: 1) { totalCount }
  }
  mergeable mergeStateStatus reviewDecision
  labels(first: 20) { nodes { name } }
  reviewRequests(first: 20) { nodes { requestedReviewer { ... on User { login } ... on Team { slug } } } }
  latestReviews(first: 20) { nodes { author { login } state } }
  latestOpinionatedReviews(first: 20) { nodes { author { login } state commit { oid } } }
  timelineItems(itemTypes: [REVIEW_REQUESTED_EVENT, READY_FOR_REVIEW_EVENT], last: 50) { nodes {
    __typename
    ... on ReviewRequestedEvent { createdAt requestedReviewer { ... on User { login } } }
    ... on ReadyForReviewEvent { createdAt }
  } }
  myReviews: reviews(author: $me, last: 20) { nodes { state submittedAt commit { oid } comments { totalCount } } }
  reviewThreads(first: 100) { nodes { isResolved comments(first: 1) { nodes { author { login } pullRequestReview { state } } } } }
  commits(last: 1) { nodes { commit { committedDate statusCheckRollup { state contexts(first: 100) { totalCount nodes {
    ... on CheckRun { name status conclusion startedAt checkSuite { workflowRun { databaseId } } }
    ... on StatusContext { context state createdAt }
  } } } } } }
}'
# GitHub times out a search that returns 100 of these PRs in one response, so
# read the results in pages of SEARCH_PAGE, up to SEARCH_LIMIT in all.
SEARCH_PAGE=25
SEARCH_LIMIT=100
SEARCH_QUERY="query(\$q: String!, \$me: String!, \$after: String) {
  search(query: \$q, type: ISSUE, first: $SEARCH_PAGE, after: \$after) {
    issueCount pageInfo { hasNextPage endCursor } nodes { ...PR }
  }
}"
PR_QUERY='query($owner: String!, $name: String!, $number: Int!, $me: String!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) { ...PR } }
}'

graphql() {
  gh api graphql -f query="$1 $FRAGMENT" -f me="$me" "${@:2}"
}

# Bash clears set -e inside command substitutions, so every function that runs
# inside one returns its failures explicitly.
search() {
  local q=$1 out count more cursor="" seen=0
  while :; do
    out=$(graphql "$SEARCH_QUERY" -f q="$q" ${cursor:+-f "after=$cursor"}) || return
    if [ "$seen" -eq 0 ]; then
      count=$(jq '.data.search.issueCount' <<< "$out") || return
      if [ "$count" -gt "$SEARCH_LIMIT" ]; then
        echo "warning: only the first $SEARCH_LIMIT of $count results for: $q" >&2
      fi
    fi
    jq '.data.search.nodes[]' <<< "$out" || return
    seen=$((seen + SEARCH_PAGE))
    more=$(jq -r '.data.search.pageInfo.hasNextPage // false' <<< "$out") || return
    [ "$more" = true ] && [ "$seen" -lt "$SEARCH_LIMIT" ] || return 0
    cursor=$(jq -r '.data.search.pageInfo.endCursor' <<< "$out") || return
  done
}

# gh skips --jq and prints the raw error body when a call fails, so capture the
# output and print it only on success.
read_ref() {
  local ref=$1 slug node
  slug=${ref%%#*}
  if node=$(graphql "$PR_QUERY" -f owner="${slug%%/*}" -f name="${slug#*/}" \
    -F number="${ref##*#}" --jq '.data.repository.pullRequest'); then
    printf '%s\n' "$node"
  else
    echo "warning: cannot read $ref" >&2
  fi
}

# A cancelled duplicate run leaves its checks on the head commit, so the rollup
# reads FAILURE although the run that replaced it passed. Print the IDs of runs
# that a newer run of the same workflow and event on the same head replaced. A
# skipped run replaces nothing: a workflow that skips its jobs for some PR
# actions, such as adding a label, would otherwise hide an earlier failure.
superseded_runs() {
  local slug=$1 sha=$2 ids
  if ids=$(gh api "repos/$slug/actions/runs?head_sha=$sha&per_page=100" \
    --jq '[.workflow_runs | group_by([.workflow_id, .event])[] | sort_by(.id)
      | ([.[] | select(.conclusion != "skipped") | .id] | last) as $latest
      | .[] | select($latest != null and .id < $latest) | .id]'); then
    jq -n --arg key "$slug@$sha" --argjson ids "$ids" '{key: $key, value: $ids}'
  else
    echo "warning: cannot list workflow runs for $slug@$sha" >&2
  fi
}

# A failing check counts against readiness only when branch protection requires
# it. GitHub reports BLOCKED ahead of UNSTABLE while a required approval is
# missing, so the merge state cannot say which checks are required. Print the
# names of the required checks on the PR's head. isRequired needs the PR number,
# so this is one query per PR.
REQUIRED_QUERY='query($owner: String!, $name: String!, $number: Int!) {
  repository(owner: $owner, name: $name) { pullRequest(number: $number) { commits(last: 1) { nodes { commit {
    statusCheckRollup { contexts(first: 100) { nodes {
      ... on CheckRun { name isRequired(pullRequestNumber: $number) }
      ... on StatusContext { context isRequired(pullRequestNumber: $number) }
    } } }
  } } } } }
}'
required_checks() {
  local slug=$1 number=$2 names
  if names=$(gh api graphql -f query="$REQUIRED_QUERY" -f owner="${slug%%/*}" -f name="${slug#*/}" \
    -F number="$number" --jq '[.data.repository.pullRequest.commits.nodes[0].commit.statusCheckRollup.contexts.nodes[]
      | select(.isRequired) | .name // .context] | unique'); then
    jq -n --arg key "$slug#$number" --argjson names "$names" '{key: $key, value: $names}'
  else
    echo "warning: cannot read the required checks for $slug#$number" >&2
  fi
}

# A failed search fails the run; an unreadable ref only warns.
collect_prs() {
  search "is:pr is:open archived:false user-review-requested:@me$scope" || return
  if [ -n "$since" ]; then
    search "is:pr reviewed-by:@me -author:@me updated:>=$since$scope" || return
    search "is:pr is:closed user-review-requested:@me closed:>=$since$scope" || return
  fi
  for ref in ${refs[@]+"${refs[@]}"}; do
    read_ref "$ref"
  done
}

# Without --repo or --all-repos, search only the repository the current
# directory belongs to, as gh resolves it from the git remotes.
if [ -z "$repo" ] && [ "$all_repos" = false ]; then
  repo=$(gh repo view --json nameWithOwner --jq .nameWithOwner) && [[ $repo =~ $repo_re ]] \
    || usage_error "cannot find the current directory's GitHub repository; run it inside one, or pass --repo OWNER/NAME or --all-repos"
fi

# Take the time first, so passing it as the next --since misses nothing.
checked_at=$(date -u +%FT%TZ)
me=$(gh api user --jq .login)
scope=${repo:+ repo:$repo}
prs=$(collect_prs | jq -s 'unique_by(.url)')

jq -r '.[] | .commits.nodes[0].commit.statusCheckRollup.contexts.totalCount as $n
    | select(($n // 0) > 100)
    | "warning: only the first 100 of \($n) checks read for \(.repository.nameWithOwner)#\(.number)"' \
  <<< "$prs" >&2

superseded=$(jq -r '.[]
    | select(.state == "OPEN" and (.commits.nodes[0].commit.statusCheckRollup.state // "SUCCESS") != "SUCCESS")
    | "\(.repository.nameWithOwner) \(.headRefOid)"' <<< "$prs" \
  | while read -r slug sha; do
    superseded_runs "$slug" "$sha"
  done | jq -s 'from_entries')

required=$(jq -r '.[]
    | select(.state == "OPEN" and ((.commits.nodes[0].commit.statusCheckRollup.state // "") | IN("FAILURE", "ERROR")))
    | "\(.repository.nameWithOwner) \(.number)"' <<< "$prs" \
  | while read -r slug number; do
    required_checks "$slug" "$number"
  done | jq -s 'from_entries')

SUMMARY='
def result: .conclusion // .state;
def failed: result | IN("FAILURE", "ERROR", "TIMED_OUT", "STARTUP_FAILURE", "ACTION_REQUIRED");
def running: (.status // "COMPLETED") != "COMPLETED" or ((.state // "") | IN("PENDING", "EXPECTED"));
def rollup_ci: if IN("FAILURE", "ERROR") then "failing" elif IN("PENDING", "EXPECTED") then "running" else null end;
# A label that says the author is not done, such as "WIP" or "do-not-merge".
def unfinished_label: test("\\b(wip|dnm|work[ -]in[ -]progress|not[ -]ready|do[ -]not[ -](merge|review)|don.?t[ -](merge|review))\\b"; "i");
# A title says so only with a marker: a prefix that ends in a colon, a bracketed
# tag, or the words in capitals. A title such as "fix: do not merge duplicate
# rows" describes the change instead.
def unfinished_title:
  "wip|dnm|draft|work in progress|do not (merge|review)" as $marker
  | test("^\\s*\\[?(\($marker))\\]?:|\\[(\($marker))\\]"; "i")
    or test("\\b(WIP|DNM|DO NOT (MERGE|REVIEW))\\b");
def elapsed: if . < 3600 then "\(. / 60 | floor)m"
  elif . < 86400 then "\(. / 3600 | floor)h"
  elif . < 7 * 86400 then "\(. / 86400 | floor)d \((. % 86400) / 3600 | floor)h"
  else "\(. / 86400 | floor)d" end;
# A check still pending after this many seconds is a gate, such as a sign-off, or
# is stuck. It is not CI in progress.
def gate_after: 7200;
($checkedAt | fromdateiso8601) as $now |
{checkedAt: $checkedAt, me: $me, prs: (sort_by(.repository.nameWithOwner, .number) | map(
  .commits.nodes[0].commit as $c
  | ($c.statusCheckRollup.contexts.nodes // []) as $all
  | ($superseded["\(.repository.nameWithOwner)@\(.headRefOid)"] // []) as $old
  | [$all[] | select((.checkSuite.workflowRun.databaseId // -1) | IN($old[]) | not)] as $checks
  # Checks past the first 100 are unread, so a failure among them shows only in
  # the rollup state; let that state outrank a verdict from the checks read.
  | (($c.statusCheckRollup.contexts.totalCount // ($all | length)) - ($all | length)) as $unread
  | (if $unread > 0 then $c.statusCheckRollup.state | rollup_ci else null end) as $rollupCi
  # A thread reply outside a review is a submitted COMMENTED review of its own,
  # so a reply must not hide an earlier approval or changes request.
  | [.myReviews.nodes[] | select(.state != "PENDING")] as $submitted
  | ([$submitted[] | select(.state != "COMMENTED")] | last // ($submitted | last)) as $mine
  | any(.reviewRequests.nodes[]; .requestedReviewer.login == $me) as $requested
  # A reviewer who approves or requests changes and then comments has COMMENTED
  # as their latest review, so read their latest approval or changes request
  # first and their latest review only when they have neither.
  | (.latestOpinionatedReviews.nodes // []) as $decisive
  | ($decisive + [.latestReviews.nodes[] | select(.author.login as $login | all($decisive[]; .author.login != $login))]) as $reviews
  # The first issue key in the title, else the first Linear link in the
  # description, else the first key the description names after a linking word,
  # as in "Fixes WID-42", else a key that starts a segment of the branch name, as
  # in "ana/wid-42-cache-lookups".
  | ([(.body // "") | match("https://linear\\.app/[A-Za-z0-9_-]+/issue/([A-Za-z][A-Za-z0-9]*-[0-9]+)[A-Za-z0-9/_-]*"; "g")
      | {key: (.captures[0].string | ascii_upcase), url: .string}]) as $links
  | ([.title | scan("\\b[A-Z][A-Z0-9]+-[0-9]+\\b")] | first) as $titleKey
  | ([(.body // "") | match("\\b(?i:close[sd]?|closing|fix(?:e[sd])?|fixing|resolve[sd]?|resolving|complete[sd]?|completing|refs?|references|part of|related to|contributes to|towards?):? +\\[?([A-Z][A-Z0-9]*-[0-9]+)\\b"; "g")
      | .captures[0].string] | first) as $namedKey
  # A dependency bot names its branch after the package and version, as in
  # "dependabot/github_actions/actions/checkout-4", so its branch names no issue.
  | ([(.headRefName // "") | select(test("^(dependabot|renovate)/") | not)
      | match("(?:^|/)([A-Za-z][A-Za-z0-9]*-[0-9]+)(?=$|[/_-])"; "g")
      | .captures[0].string | ascii_upcase] | first) as $branchKey
  | (if $titleKey then {key: $titleKey, source: "title"}
     elif $links[0] then {key: $links[0].key, source: "description"}
     elif $namedKey then {key: $namedKey, source: "description"}
     elif $branchKey then {key: $branchKey, source: "branch"}
     else null end) as $issue
  # You have waited since the author last requested you, or since the PR left
  # draft after that. The creation time stands in when the request is older than
  # the events read.
  | ([.timelineItems.nodes[]? | select(.__typename == "ReviewRequestedEvent" and .requestedReviewer.login == $me) | .createdAt] | last) as $requestedAt
  | ([.timelineItems.nodes[]? | select(.__typename == "ReadyForReviewEvent") | .createdAt] | last) as $readyAt
  | (if ($requested and .state == "OPEN") | not then null
     elif $requestedAt == null then {since: .createdAt, from: "opened"}
     elif $readyAt != null and $readyAt > $requestedAt then {since: $readyAt, from: "marked ready"}
     else {since: $requestedAt, from: "requested"} end) as $waiting
  | ((if ($checks | length) == 0 then "none"
      elif any($checks[]; failed) then "failing"
      elif any($checks[]; running) then "running"
      elif any($checks[]; result == "CANCELLED") then "cancelled"
      else "green" end) as $read
     | if $rollupCi == "failing" or ($rollupCi == "running" and $read != "failing") then $rollupCi
       else $read end) as $ci
  | ([.reviewThreads.nodes[] | select((.isResolved | not) and .comments.nodes[0].author.login != $me)] | length) as $otherThreads
  | [$checks[] | select(running) | (.startedAt // .createdAt)] as $pendingSince
  | ($ci == "running" and (($pendingSince | length) == 0
      or any($pendingSince[]; . == null or $now - fromdateiso8601 < gate_after))) as $ciInMotion
  # The open PR whose branch this PR targets. GitHub also lists fork PRs from a
  # branch of the same name, and a long-lived branch such as development can be
  # the head of a release PR, so skip fork PRs, the default branch, and branches
  # that branch protection or a ruleset covers.
  | (if .baseRefName == .repository.defaultBranchRef.name
        or .baseRef.refUpdateRule != null or (.baseRef.rules.totalCount // 0) > 0 then null
     else .repository.nameWithOwner as $repo
       | first(.baseRef.associatedPullRequests.nodes[]? | select(.headRepository.nameWithOwner == $repo)) // null
     end) as $basePr
  # Whether a failing check is one that branch protection requires. Without the
  # required checks, UNSTABLE is the only sign that none is, and a failure that
  # no check read names counts as required.
  | [$checks[] | select(failed) | .name // .context] as $failedNames
  | $required["\(.repository.nameWithOwner)#\(.number)"] as $requiredNames
  | ($ci == "failing" and (if $requiredNames == null then .mergeStateStatus != "UNSTABLE"
      elif ($failedNames | length) == 0 then true
      else any($failedNames[]; IN($requiredNames[])) end)) as $requiredFailing
  | ([if .isDraft then "draft" else empty end,
      if .title | unfinished_title then "title says unfinished" else empty end,
      (.labels.nodes[]?.name | select(unfinished_label) | "label \(.)"),
      if .mergeStateStatus == "DIRTY" or .mergeable == "CONFLICTING" then "merge conflicts" else empty end,
      if $requiredFailing then "CI failing" else empty end,
      (.headRefOid as $head | $decisive[]
        | select(.author.login != $me and .state == "CHANGES_REQUESTED" and .commit.oid == $head)
        | "changes requested by \(.author.login), no push since")]) as $blockers
  | ([if $ci == "failing" and ($requiredFailing | not) then "a check that is not required is failing"
      elif $ciInMotion then "CI running"
      elif $ci == "cancelled" then "CI cancelled"
      elif $ci == "none" and .mergeStateStatus != "DIRTY" then "no CI checks"
      else empty end,
      if $otherThreads == 1 then "1 unresolved thread from others"
      elif $otherThreads > 1 then "\($otherThreads) unresolved threads from others"
      else empty end,
      if $basePr then "stacked on #\($basePr.number)" else empty end,
      if (.body // "") | test("\\S") | not then "no description" else empty end,
      if .mergeStateStatus == "UNKNOWN" then "merge state unknown" else empty end]) as $cautions
  | {
      pr: "\(.repository.nameWithOwner)#\(.number)", url, title,
      issue: $issue.key, issueSource: $issue.source,
      issueUrl: (first($links[] | select(.key == $issue.key) | .url) // null),
      author: .author.login, state, mergedAt, mergedBy: .mergedBy.login, draft: .isDraft,
      size: "+\(.additions)/-\(.deletions) in \(.changedFiles) files",
      base: .baseRefName, defaultBranch: .repository.defaultBranchRef.name,
      basePr: (if $basePr then {number: $basePr.number, url: $basePr.url, draft: $basePr.isDraft} else null end),
      headBranch: .headRefName, head: .headRefOid, lastCommitAt: $c.committedDate,
      requestedOfMe: $requested,
      waitingSince: $waiting.since, waitingFrom: $waiting.from,
      waiting: (if $waiting then [$now - ($waiting.since | fromdateiso8601), 0] | max | elapsed else null end),
      readiness: (if .state != "OPEN" then null else {
        verdict: (if ($blockers | length) > 0 then "not-ready" elif ($cautions | length) > 0 then "check" else "ready" end),
        blockers: $blockers, cautions: $cautions} end),
      requestedTeams: [.reviewRequests.nodes[].requestedReviewer.slug // empty],
      myPendingComments: ([.myReviews.nodes[] | select(.state == "PENDING") | .comments.totalCount] | add // 0),
      myLastReview: (if $mine then {state: $mine.state, at: $mine.submittedAt, onHead: ($mine.commit.oid == .headRefOid)} else null end),
      myOpenThreads: [.reviewThreads.nodes[] | select((.isResolved | not)
        and .comments.nodes[0].author.login == $me
        and .comments.nodes[0].pullRequestReview.state != "PENDING")] | length,
      otherOpenThreads: $otherThreads,
      otherReviews: [$reviews[] | select(.author.login != $me) | "\(.author.login): \(.state)"],
      reviewDecision, mergeable, mergeStateStatus,
      ci: $ci,
      failing: [$checks[] | select(failed) | {name: (.name // .context), run: .checkSuite.workflowRun.databaseId}] | unique,
      running: [$checks[] | select(running) | {name: (.name // .context), since: (.startedAt // .createdAt)}] | unique,
      cancelled: [$checks[] | select(result == "CANCELLED") | .name] | unique,
      supersededChecks: (($all | length) - ($checks | length)),
      unreadChecks: $unread,
      # The first message of a chat that reviews this PR, for each host that can run it.
      reviewCommand: {claude: "/trackbed:pr-github-review \(.url)", codex: "$trackbed:pr:github-review \(.url)"}
    }
))}'

jq --arg me "$me" --arg checkedAt "$checked_at" --argjson superseded "$superseded" --argjson required "$required" \
  "$SUMMARY" <<< "$prs"
