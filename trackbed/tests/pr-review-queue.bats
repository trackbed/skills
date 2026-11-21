#!/usr/bin/env bats

bats_require_minimum_version 1.5.0

load 'test_helper/common'

ME="riley-reviewer"
HEAD="1111111111111111111111111111111111111111"
OLD_HEAD="0000000000000000000000000000000000000000"

# jq helpers for building GitHub-shaped fixtures.
JQ_DEFS='
def check($name; $conclusion; $run):
  {name: $name, status: "COMPLETED", conclusion: $conclusion, startedAt: "2026-04-01T09:00:00Z",
   checkSuite: {workflowRun: {databaseId: $run}}};
def rollup($state; $checks):
  .commits.nodes[0].commit.statusCheckRollup = {state: $state, contexts: {nodes: $checks}};
def review($state; $oid; $comments):
  {state: $state, submittedAt: (if $state == "PENDING" then null else "2026-04-01T10:00:00Z" end),
   commit: {oid: $oid}, comments: {totalCount: $comments}};
def thread($resolved; $login; $review_state):
  {isResolved: $resolved, comments: {nodes: [{author: {login: $login}, pullRequestReview: {state: $review_state}}]}};
def workflow_run($id; $workflow; $event): {id: $id, workflow_id: $workflow, name: "CI", event: $event};
def requested($login; $at): {__typename: "ReviewRequestedEvent", createdAt: $at, requestedReviewer: {login: $login}};
def marked_ready($at): {__typename: "ReadyForReviewEvent", createdAt: $at};
def minutes_ago($n): now - $n * 60 | todate;
def same_repo_pr($number; $draft):
  {number: $number, url: "https://github.com/acme/widgets/pull/\($number)", isDraft: $draft,
   headRepository: {nameWithOwner: "acme/widgets"}};
def fork_pr($number):
  {number: $number, url: "https://github.com/someone/widgets/pull/\($number)", isDraft: false,
   headRepository: {nameWithOwner: "someone/widgets"}};
'

# An open PR that requests $ME personally and the platform team, with a
# description, no labels, reviews or threads, and one green check.
BASE_PR='{
  number: $number,
  title: "WID-42: Cache widget lookups",
  body: "Caches widget lookups for an hour.",
  isDraft: false, state: "OPEN", createdAt: "2026-03-30T08:00:00Z", mergedAt: null, mergedBy: null,
  repository: {nameWithOwner: "acme/widgets", defaultBranchRef: {name: "main"}},
  author: {login: "ana-author"},
  baseRefName: "main", headRefName: "ana/cache-widget-lookups", headRefOid: $head,
  baseRef: {associatedPullRequests: {nodes: []}},
  additions: 120, deletions: 8, changedFiles: 5,
  mergeable: "MERGEABLE", mergeStateStatus: "BLOCKED", reviewDecision: "REVIEW_REQUIRED",
  labels: {nodes: []},
  reviewRequests: {nodes: [{requestedReviewer: {login: $me}}, {requestedReviewer: {slug: "platform"}}]},
  latestReviews: {nodes: []},
  latestOpinionatedReviews: {nodes: []},
  timelineItems: {nodes: [requested($me; "2026-04-01T08:30:00Z")]},
  myReviews: {nodes: []},
  reviewThreads: {nodes: []},
  commits: {nodes: [{commit: {committedDate: "2026-04-01T08:00:00Z", statusCheckRollup: null}}]}
} | rollup("SUCCESS"; [check("test"; "SUCCESS"; 7001)])'

setup() {
	SCRIPT="$BATS_TEST_DIRNAME/../skills/pr:review-queue/scripts/review-queue.sh"
	SKILL="$BATS_TEST_DIRNAME/../skills/pr:review-queue/SKILL.md"
	CONDUCTOR="$BATS_TEST_DIRNAME/../skills/pr:review-queue/references/conductor.md"
	TMP_DIR="$(mktemp -d)"
	BIN_DIR="$TMP_DIR/bin"
	GH_FIXTURES="$TMP_DIR/fixtures"
	GH_LOG="$TMP_DIR/gh.log"
	mkdir -p "$BIN_DIR" "$GH_FIXTURES"
	: >"$GH_LOG"
	write_gh_stub
	export PATH="$BIN_DIR:$PATH" GH_FIXTURES GH_LOG
	printf '{"login":"%s"}\n' "$ME" >"$GH_FIXTURES/user.json"
	echo acme/widgets >"$GH_FIXTURES/repo.txt"
}

teardown() {
	if [ -n "${TMP_DIR:-}" ] && [ -d "$TMP_DIR" ]; then
		rm -rf "$TMP_DIR"
	fi
}

# Serves fixtures from $GH_FIXTURES and logs one line per call to $GH_LOG.
# `gh repo view` prints the current repository from repo.txt and fails without
# it, as gh does outside a GitHub repository. Like
# gh, it applies --jq only on success and prints strings raw; on an error it
# prints the raw error body to stdout and exits 1.
write_gh_stub() {
	cat >"$BIN_DIR/gh" <<'GH'
#!/bin/sh
set -eu
if [ "${1-}" = repo ] && [ "${2-}" = view ]; then
  echo "repo view" >>"$GH_LOG"
  [ -f "$GH_FIXTURES/repo.txt" ] || {
    echo "failed to run git: fatal: not a git repository" >&2
    exit 1
  }
  cat "$GH_FIXTURES/repo.txt"
  exit 0
fi
[ "${1-}" = api ] || {
  echo "unexpected gh call: $*" >&2
  exit 97
}
endpoint=$2
file=""
shift 2
q="" after="" owner="" name="" number="" filter="" query=""
while [ $# -gt 0 ]; do
  case "$1" in
    -f | -F)
      case "$2" in
        q=*) q=${2#q=} ;;
        after=*) after=${2#after=} ;;
        owner=*) owner=${2#owner=} ;;
        name=*) name=${2#name=} ;;
        number=*) number=${2#number=} ;;
        query=*) query=${2#query=} ;;
      esac
      shift 2
      ;;
    --jq)
      filter=$2
      shift 2
      ;;
    *) shift ;;
  esac
done

fail() {
  printf '%s\n' "$1"
  printf 'gh: %s\n' "$2" >&2
  exit 1
}

case "$endpoint" in
  user)
    echo user >>"$GH_LOG"
    file=$GH_FIXTURES/user.json
    ;;
  graphql)
    case "$query" in
      *isRequired*)
        printf 'required %s/%s#%s\n' "$owner" "$name" "$number" >>"$GH_LOG"
        file=$GH_FIXTURES/required-$owner-$name-$number.json
        [ -f "$file" ] || fail '{"errors":[{"message":"Something went wrong"}]}' "Something went wrong"
        ;;
    esac
    if [ -n "$file" ]; then
      :
    elif [ -n "$q" ]; then
      printf 'search %s%s\n' "$q" "${after:+ after=$after}" >>"$GH_LOG"
      case "$q" in
        *reviewed-by:@me*) kind=reviewed ;;
        *is:closed*) kind=closed ;;
        *) kind=open ;;
      esac
      [ ! -f "$GH_FIXTURES/search-$kind.error" ] || fail "$(cat "$GH_FIXTURES/search-$kind.error")" "search failed"
      file=$GH_FIXTURES/search-$kind${after:+-$after}.json
      [ -f "$file" ] || {
        printf '%s\n' '{"data":{"search":{"issueCount":0,"nodes":[]}}}'
        exit 0
      }
    else
      printf 'pr %s/%s#%s\n' "$owner" "$name" "$number" >>"$GH_LOG"
      file=$GH_FIXTURES/pr-$owner-$name-$number.json
      [ -f "$file" ] || fail '{"data":{"repository":{"pullRequest":null}},"errors":[{"type":"NOT_FOUND","message":"Could not resolve to a PullRequest."}]}' "Could not resolve to a PullRequest."
    fi
    ;;
  repos/*/actions/runs*)
    printf 'runs %s\n' "$endpoint" >>"$GH_LOG"
    sha=${endpoint#*head_sha=}
    file=$GH_FIXTURES/runs-${sha%%&*}.json
    [ -f "$file" ] || fail '{"message":"Not Found","status":"404"}' "Not Found (HTTP 404)"
    ;;
  *)
    echo "unexpected gh api endpoint: $endpoint" >&2
    exit 97
    ;;
esac

if [ -n "$filter" ]; then
  jq -r "$filter" "$file"
else
  cat "$file"
fi
GH
	chmod +x "$BIN_DIR/gh"
}

# Prints PR <number> from BASE_PR after applying the jq filter given last, which
# can use $me, $head, $old_head, and the JQ_DEFS helpers. Arguments between the
# number and the filter go to jq, such as --arg link <url>.
pr_node() {
	local number=$1 filter=.
	shift
	if [ $# -gt 0 ]; then
		filter=${!#}
		set -- "${@:1:$#-1}"
	fi
	jq -n --arg me "$ME" --arg head "$HEAD" --arg old_head "$OLD_HEAD" --argjson number "$number" "$@" \
		"$JQ_DEFS $BASE_PR | $filter"' | .url = "https://github.com/\(.repository.nameWithOwner)/pull/\(.number)"'
}

# Serves the PR nodes given after <kind> as the open, reviewed, or closed search.
serve_search() {
	local kind=$1
	shift
	printf '%s\n' "$@" | jq -s '{data: {search: {issueCount: length, nodes: .}}}' >"$GH_FIXTURES/search-$kind.json"
}

# Serves one page of the <kind> search: the page after cursor <after> (empty for
# the first page), reporting <total> results and the cursor <next> of the next
# page (empty for the last page), with the PR nodes given after <next>.
serve_search_page() {
	local kind=$1 after=$2 total=$3 next=$4
	shift 4
	printf '%s\n' "$@" | jq -s --argjson total "$total" --arg next "$next" '{data: {search: {issueCount: $total,
		pageInfo: {hasNextPage: ($next != ""), endCursor: (if $next == "" then null else $next end)}, nodes: .}}}' \
		>"$GH_FIXTURES/search-$kind${after:+-$after}.json"
}

# Serves a PR node for the ref OWNER/NAME#N.
serve_pr() {
	local ref=$1 slug=${1%%#*}
	jq '{data: {repository: {pullRequest: .}}}' <<<"$2" >"$GH_FIXTURES/pr-${slug%%/*}-${slug#*/}-${ref##*#}.json"
}

# Serves the required checks of PR OWNER/NAME#N: each check name given after the
# ref is required, and the check "optional-lint" is not.
serve_required() {
	local ref=$1 slug=${1%%#*}
	shift
	printf '%s\n' "$@" | jq -R '{name: ., isRequired: true}' | jq -s '. + [{name: "optional-lint", isRequired: false}]
		| {data: {repository: {pullRequest: {commits: {nodes: [{commit: {statusCheckRollup: {contexts: {nodes: .}}}}]}}}}}' \
		>"$GH_FIXTURES/required-${slug%%/*}-${slug#*/}-${ref##*#}.json"
}

# Serves the workflow runs for head SHA $1 from the jq array expression $2.
serve_runs() {
	jq -n "$JQ_DEFS {workflow_runs: $2} | .total_count = (.workflow_runs | length)" >"$GH_FIXTURES/runs-$1.json"
}

# Runs the script through /bin/bash, which is Bash 3.2 on macOS.
run_queue() {
	run --separate-stderr /bin/bash "$SCRIPT" "$@"
}

# Asserts that the script's stderr contains $1. Unlike a mid-test [[ ]], a plain
# command fails the test even when Bats runs under Bash 3.2.
assert_stderr_contains() {
	grep -Fq -- "$1" <<<"$stderr" || {
		printf 'expected stderr to contain %s, got: %s\n' "$1" "$stderr" >&2
		return 1
	}
}

# Asserts that the jq filter $1, applied to the script's stdout, prints $2.
assert_json() {
	local actual
	actual=$(jq -c -r "$1" <<<"$output")
	if [ "$actual" != "$2" ]; then
		printf 'expected %s to print %s, got %s\n' "$1" "$2" "$actual" >&2
		return 1
	fi
}

@test "searches the current repository for PRs that request you personally" {
	serve_search open "$(pr_node 101)"

	run_queue

	[ "$status" -eq 0 ]
	diff -u - "$GH_LOG" <<'EOF'
repo view
user
search is:pr is:open archived:false user-review-requested:@me repo:acme/widgets
EOF
	assert_json '.me' "$ME"
	assert_json '.checkedAt | test("^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$")' true
	assert_json '.prs | length' 1
	assert_json '.prs[0] | [.pr, .issue, .author, .size, .base, .defaultBranch]' \
		'["acme/widgets#101","WID-42","ana-author","+120/-8 in 5 files","main","main"]'
	assert_json '.prs[0] | [.requestedOfMe, .requestedTeams, .myLastReview, .myPendingComments, .ci]' \
		'[true,["platform"],null,0,"green"]'
	assert_json '.prs[0] | [.title, .url, .headBranch]' \
		'["WID-42: Cache widget lookups","https://github.com/acme/widgets/pull/101","ana/cache-widget-lookups"]'
}

@test "--all-repos searches every repository without looking up the current one" {
	rm "$GH_FIXTURES/repo.txt"
	serve_search open "$(pr_node 101)" "$(pr_node 7 '.repository.nameWithOwner = "acme/gadgets"')"

	run_queue --all-repos

	[ "$status" -eq 0 ]
	diff -u - "$GH_LOG" <<'EOF'
user
search is:pr is:open archived:false user-review-requested:@me
EOF
	assert_json '[.prs[].pr]' '["acme/gadgets#7","acme/widgets#101"]'
}

@test "outside a GitHub repository, asks for --repo or --all-repos instead of searching" {
	rm "$GH_FIXTURES/repo.txt"

	run_queue

	[ "$status" -eq 2 ]
	assert_stderr_contains "pass --repo OWNER/NAME or --all-repos"
	[ -z "$output" ]
	diff -u - "$GH_LOG" <<<'repo view'
}

@test "--since adds searches for PRs you reviewed and PRs closed since then" {
	serve_search open "$(pr_node 101)"
	serve_search reviewed "$(pr_node 102 '.reviewRequests.nodes = [] | .myReviews.nodes = [review("APPROVED"; $head; 0)]')"
	serve_search closed "$(pr_node 103 '.state = "MERGED" | .mergedAt = "2026-04-02T12:00:00Z"
		| .mergedBy = {login: "mo-merger"} | rollup("FAILURE"; [check("test"; "FAILURE"; 7002)])')"

	run_queue --repo acme/widgets --since 2026-04-01T09:30:00Z

	[ "$status" -eq 0 ]
	diff -u - "$GH_LOG" <<'EOF'
user
search is:pr is:open archived:false user-review-requested:@me repo:acme/widgets
search is:pr reviewed-by:@me -author:@me updated:>=2026-04-01T09:30:00Z repo:acme/widgets
search is:pr is:closed user-review-requested:@me closed:>=2026-04-01T09:30:00Z repo:acme/widgets
EOF
	assert_json '[.prs[].pr]' '["acme/widgets#101","acme/widgets#102","acme/widgets#103"]'
	assert_json '.prs[1] | [.requestedOfMe, .myLastReview.state, .myLastReview.onHead]' '[false,"APPROVED",true]'
	assert_json '.prs[2] | [.state, .mergedBy, .requestedOfMe, .myLastReview]' '["MERGED","mo-merger",true,null]'
	# Only an open PR that still requests you is waiting on you, and only an open
	# PR has a readiness estimate.
	assert_json '.prs[1] | [.waiting, .waitingSince, .readiness.verdict]' '[null,null,"ready"]'
	assert_json '.prs[2] | [.waiting, .waitingSince, .readiness]' '[null,null,null]'
}

@test "re-queries refs by number and de-duplicates the combined results by URL" {
	serve_search open "$(pr_node 101)"
	serve_pr acme/widgets#101 "$(pr_node 101)"
	serve_pr acme/gadgets#7 "$(pr_node 7 '.repository.nameWithOwner = "acme/gadgets" | .title = "Tidy gadget logs"')"

	run_queue acme/widgets#101 acme/gadgets#7

	[ "$status" -eq 0 ]
	grep -qx 'pr acme/widgets#101' "$GH_LOG"
	grep -qx 'pr acme/gadgets#7' "$GH_LOG"
	assert_json '[.prs[].pr]' '["acme/gadgets#7","acme/widgets#101"]'
	assert_json '.prs[0].issue' null
}

@test "reads search results in pages and follows the cursor" {
	serve_search_page open "" 2 c1 "$(pr_node 101)"
	serve_search_page open c1 2 "" "$(pr_node 102)"

	run_queue

	[ "$status" -eq 0 ]
	diff -u - "$GH_LOG" <<'EOF'
repo view
user
search is:pr is:open archived:false user-review-requested:@me repo:acme/widgets
search is:pr is:open archived:false user-review-requested:@me repo:acme/widgets after=c1
EOF
	assert_json '[.prs[].pr]' '["acme/widgets#101","acme/widgets#102"]'
	[ -z "$stderr" ]
}

@test "stops paging at 100 results and warns about the rest" {
	serve_search_page open "" 130 c1 "$(pr_node 101)"
	serve_search_page open c1 130 c2 "$(pr_node 102)"
	serve_search_page open c2 130 c3 "$(pr_node 103)"
	serve_search_page open c3 130 c4 "$(pr_node 104)"

	run_queue

	[ "$status" -eq 0 ]
	[ "$(grep -c '^search ' "$GH_LOG")" -eq 4 ]
	[ -z "$(grep 'after=c4' "$GH_LOG")" ]
	assert_stderr_contains "warning: only the first 100 of 130 results for: is:pr is:open archived:false user-review-requested:@me repo:acme/widgets"
	assert_json '.prs | length' 4
}

@test "an unreadable ref warns and leaves the rest of the report intact" {
	serve_search open "$(pr_node 101)"

	run_queue acme/widgets#999

	[ "$status" -eq 0 ]
	assert_stderr_contains "warning: cannot read acme/widgets#999"
	assert_json '[.prs[].pr]' '["acme/widgets#101"]'
}

@test "a failed search fails the run instead of printing a partial queue" {
	serve_search open "$(pr_node 101)"
	printf '%s\n' '{"errors":[{"message":"API rate limit exceeded"}]}' >"$GH_FIXTURES/search-reviewed.error"

	run_queue --since 2026-04-01

	[ "$status" -ne 0 ]
	[ -z "$output" ]
}

@test "drops checks from runs that a newer run of the same workflow and event replaced" {
	serve_search open "$(pr_node 101 'rollup("FAILURE";
		[check("test"; "CANCELLED"; 7001), check("test"; "SUCCESS"; 7002), check("lint"; "SUCCESS"; 7003)])')"
	serve_runs "$HEAD" '[workflow_run(7003; 12; "pull_request"),
		workflow_run(7002; 11; "pull_request"), workflow_run(7001; 11; "pull_request")]'

	run_queue

	[ "$status" -eq 0 ]
	grep -qx "runs repos/acme/widgets/actions/runs?head_sha=$HEAD&per_page=100" "$GH_LOG"
	assert_json '.prs[0] | [.ci, .supersededChecks, .cancelled, .failing]' '["green",1,[],[]]'
}

@test "a skipped run does not replace an earlier run of the same workflow and event" {
	serve_search open "$(pr_node 101 'rollup("FAILURE"; [check("test"; "FAILURE"; 7001), check("test"; "SKIPPED"; 7002),
		check("label"; "SKIPPED"; 7003), check("label"; "SUCCESS"; 7004)])')"
	serve_runs "$HEAD" '[workflow_run(7004; 12; "pull_request"), workflow_run(7003; 12; "pull_request") + {conclusion: "skipped"},
		workflow_run(7002; 11; "pull_request") + {conclusion: "skipped"}, workflow_run(7001; 11; "pull_request") + {conclusion: "failure"}]'

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.ci, .supersededChecks, .failing]' '["failing",1,[{"name":"test","run":7001}]]'
}

@test "keeps checks from other workflows and events, even when they share a workflow name" {
	serve_search open "$(pr_node 101 'rollup("FAILURE"; [check("build"; "FAILURE"; 7000),
		check("lint"; "FAILURE"; 7001), check("test"; "CANCELLED"; 7002), check("test"; "SUCCESS"; 7003)])')"
	serve_runs "$HEAD" '[workflow_run(7003; 11; "pull_request"), workflow_run(7002; 11; "pull_request"),
		workflow_run(7001; 12; "pull_request"), workflow_run(7000; 11; "push")]'

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.ci, .supersededChecks, .cancelled]' '["failing",1,[]]'
	assert_json '.prs[0].failing' '[{"name":"build","run":7000},{"name":"lint","run":7001}]'
}

@test "a failed workflow-run lookup warns and counts every check" {
	serve_search open "$(pr_node 101 'rollup("FAILURE"; [check("test"; "CANCELLED"; 7001), check("test"; "SUCCESS"; 7002)])')"

	run_queue

	[ "$status" -eq 0 ]
	assert_stderr_contains "warning: cannot list workflow runs for acme/widgets@$HEAD"
	assert_json '.prs[0] | [.ci, .supersededChecks, .cancelled]' '["cancelled",0,["test"]]'
}

@test "reports ci none without a run lookup when the head commit has no checks" {
	serve_search open "$(pr_node 101 '.commits.nodes[0].commit.statusCheckRollup = null | .mergeStateStatus = "DIRTY"')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.ci, .failing, .running]' '["none",[],[]]'
	[ -z "$(grep '^runs ' "$GH_LOG")" ]
}

@test "counts your unsubmitted pending review and leaves its threads out of your open threads" {
	serve_search open "$(pr_node 101 '
		.myReviews.nodes = [review("COMMENTED"; $head; 1), review("PENDING"; $head; 3)]
		| .reviewThreads.nodes = [
			thread(false; $me; "COMMENTED"),
			thread(false; $me; "PENDING"),
			thread(true; $me; "COMMENTED"),
			thread(false; "ana-author"; "COMMENTED")
		]')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.myPendingComments, .myOpenThreads, .otherOpenThreads, .myLastReview.state]' \
		'[3,1,1,"COMMENTED"]'
}

@test "flags an approval that a later push made stale" {
	serve_search open \
		"$(pr_node 101 '.myReviews.nodes = [review("APPROVED"; $old_head; 0)]
			| .latestReviews.nodes = [{author: {login: $me}, state: "APPROVED"}, {author: {login: "sam-second"}, state: "APPROVED"}]')" \
		"$(pr_node 102 '.myReviews.nodes = [review("APPROVED"; $head; 0)] | .reviewRequests.nodes = []')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.requestedOfMe, .myLastReview.state, .myLastReview.onHead, .otherReviews]' \
		'[true,"APPROVED",false,["sam-second: APPROVED"]]'
	assert_json '.prs[1] | [.requestedOfMe, .myLastReview.onHead]' '[false,true]'
}

@test "a thread reply after your approval does not hide that approval" {
	serve_search open "$(pr_node 101 '.myReviews.nodes = [review("CHANGES_REQUESTED"; $old_head; 2),
		review("APPROVED"; $old_head; 0), review("COMMENTED"; $head; 1)]')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0].myLastReview | [.state, .onHead]' '["APPROVED",false]'
}

@test "a failing rollup outranks the first 100 checks when more exist" {
	serve_search open "$(pr_node 101 'rollup("FAILURE"; [check("test"; "SUCCESS"; 7001)])
		| .commits.nodes[0].commit.statusCheckRollup.contexts.totalCount = 130')"
	serve_runs "$HEAD" '[workflow_run(7001; 11; "pull_request")]'

	run_queue

	[ "$status" -eq 0 ]
	assert_stderr_contains "warning: only the first 100 of 130 checks read for acme/widgets#101"
	assert_json '.prs[0] | [.ci, .unreadChecks, .failing]' '["failing",129,[]]'
}

@test "a pending rollup turns green checks read into running when more exist" {
	serve_search open "$(pr_node 101 'rollup("PENDING"; [check("test"; "SUCCESS"; 7001)])
		| .commits.nodes[0].commit.statusCheckRollup.contexts.totalCount = 101')"
	serve_runs "$HEAD" '[workflow_run(7001; 11; "pull_request")]'

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.ci, .unreadChecks]' '["running",100]'
}

@test "reports how long each PR has waited since your review was last requested" {
	serve_search open \
		"$(pr_node 101 '.timelineItems.nodes = [requested($me; "2026-03-30T09:00:00Z"),
			requested("sam-second"; minutes_ago(10)), requested($me; minutes_ago(50 * 60))]')" \
		"$(pr_node 102 '.timelineItems.nodes = [requested($me; minutes_ago(5 * 60))]')" \
		"$(pr_node 103 '.timelineItems.nodes = [requested($me; minutes_ago(40))]')" \
		"$(pr_node 104 '.timelineItems.nodes = [requested($me; minutes_ago(9 * 24 * 60 + 5 * 60))]')"

	run_queue

	[ "$status" -eq 0 ]
	# A wait of a week or more reads in whole days.
	assert_json '[.prs[] | [.waiting, .waitingFrom]]' \
		'[["2d 2h","requested"],["5h","requested"],["40m","requested"],["9d","requested"]]'
	# The latest request counts, not the first one, and not a request to someone else.
	assert_json '.prs[0].waitingSince > "2026-03-30T09:00:00Z"' true
}

@test "counts the wait from when a draft was marked ready, or from when the PR opened" {
	serve_search open \
		"$(pr_node 101 '.timelineItems.nodes = [requested($me; "2026-04-01T08:30:00Z"), marked_ready("2026-04-02T07:00:00Z")]')" \
		"$(pr_node 102 '.timelineItems.nodes = [marked_ready("2026-04-01T07:00:00Z"), requested($me; "2026-04-01T08:30:00Z")]')" \
		"$(pr_node 103 '.timelineItems.nodes = [requested("sam-second"; "2026-04-01T08:30:00Z")]')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '[.prs[] | [.waitingSince, .waitingFrom]]' \
		'[["2026-04-02T07:00:00Z","marked ready"],["2026-04-01T08:30:00Z","requested"],["2026-03-30T08:00:00Z","opened"]]'
}

@test "estimates a PR with nothing in its way as ready for review" {
	serve_search open "$(pr_node 101)"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0].readiness' '{"verdict":"ready","blockers":[],"cautions":[]}'
	assert_json '.prs[0].basePr' null
}

@test "a long-lived base branch and a check pending for hours do not count against readiness" {
	serve_search open \
		"$(pr_node 101 '.baseRefName = "development"')" \
		"$(pr_node 102 'rollup("PENDING"; [check("test"; "SUCCESS"; 7001),
			{context: "risk-signoff", state: "PENDING", createdAt: minutes_ago(3 * 60)}])')"
	serve_runs "$HEAD" '[workflow_run(7001; 11; "pull_request")]'

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.base, .defaultBranch, .basePr, .readiness.verdict]' '["development","main",null,"ready"]'
	assert_json '.prs[1] | [.ci, .running[0].name, .readiness.verdict, .readiness.cautions]' '["running","risk-signoff","ready",[]]'
}

@test "reports the open PR that a stacked PR is based on" {
	serve_search open "$(pr_node 101 '.baseRefName = "ana/widget-cache-base" | .baseRef.associatedPullRequests.nodes =
		[fork_pr(7), same_repo_pr(99; true)]')" \
		"$(pr_node 102 '.baseRefName = "ana/deleted-base" | .baseRef = null')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0].basePr' '{"number":99,"url":"https://github.com/acme/widgets/pull/99","draft":true}'
	assert_json '.prs[1] | [.basePr, .readiness.verdict]' '[null,"ready"]'
}

@test "a fork PR from a branch of the same name, or a release PR from a protected branch, is not a stack's base" {
	serve_search open \
		"$(pr_node 101 '.baseRef.associatedPullRequests.nodes = [fork_pr(7), same_repo_pr(8; false)]')" \
		"$(pr_node 102 '.baseRefName = "development" | .baseRef.associatedPullRequests.nodes = [fork_pr(7)]')" \
		"$(pr_node 103 '.baseRefName = "development" | .baseRef.refUpdateRule = {pattern: "development"}
			| .baseRef.associatedPullRequests.nodes = [same_repo_pr(9; false)]')" \
		"$(pr_node 104 '.baseRefName = "development" | .baseRef.rules = {totalCount: 2}
			| .baseRef.associatedPullRequests.nodes = [same_repo_pr(9; false)]')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '[.prs[] | [.basePr, .readiness.verdict]]' '[[null,"ready"],[null,"ready"],[null,"ready"],[null,"ready"]]'
}

@test "estimates a PR as not ready when its author still owes work" {
	serve_search open \
		"$(pr_node 101 '.isDraft = true')" \
		"$(pr_node 102 '.title = "[WIP] Cache widget lookups"')" \
		"$(pr_node 103 '.labels.nodes = [{name: "backend"}, {name: "Do Not Merge"}]')" \
		"$(pr_node 104 '.mergeable = "CONFLICTING" | .mergeStateStatus = "DIRTY" | .commits.nodes[0].commit.statusCheckRollup = null')" \
		"$(pr_node 105 'rollup("FAILURE"; [check("test"; "FAILURE"; 7001)])')" \
		"$(pr_node 106 '.latestReviews.nodes = [{author: {login: "sam-second"}, state: "COMMENTED"}]
			| .latestOpinionatedReviews.nodes = [{author: {login: "sam-second"}, state: "CHANGES_REQUESTED", commit: {oid: $head}},
				{author: {login: "kim-third"}, state: "CHANGES_REQUESTED", commit: {oid: $old_head}}]')" \
		"$(pr_node 107 '.title = "draft: cache widget lookups"')" \
		"$(pr_node 108 '.title = "Cache widget lookups, DO NOT MERGE before the freeze"')"
	serve_runs "$HEAD" '[workflow_run(7001; 11; "pull_request")]'
	serve_required "acme/widgets#105" test

	run_queue

	[ "$status" -eq 0 ]
	assert_json '[.prs[].readiness.verdict] | unique' '["not-ready"]'
	assert_json '[.prs[].readiness.blockers]' '[["draft"],["title says unfinished"],["label Do Not Merge"],["merge conflicts"],["CI failing"],["changes requested by sam-second, no push since"],["title says unfinished"],["title says unfinished"]]'
	# A conflicting PR has no checks because none ran, which the conflict already explains.
	assert_json '.prs[3].readiness.cautions' '[]'
	# A later comment does not hide a reviewer's changes request.
	assert_json '.prs[5].otherReviews' '["sam-second: CHANGES_REQUESTED","kim-third: CHANGES_REQUESTED"]'
}

@test "estimates a PR as worth a check when something is still open or in motion" {
	serve_search open \
		"$(pr_node 101 'rollup("PENDING"; [check("test"; null; 7001) + {status: "IN_PROGRESS", startedAt: minutes_ago(10)}])')" \
		"$(pr_node 102 '.reviewThreads.nodes = [thread(false; "sam-second"; "COMMENTED"), thread(false; "review-bot"; "COMMENTED"),
			thread(true; "sam-second"; "COMMENTED"), thread(false; $me; "COMMENTED")]')" \
		"$(pr_node 103 '.baseRefName = "ana/widget-cache-base" | .baseRef.associatedPullRequests.nodes =
			[same_repo_pr(99; false)]')" \
		"$(pr_node 104 '.body = "  \n" | .commits.nodes[0].commit.statusCheckRollup = null')" \
		"$(pr_node 105 '.title = "fix: do not merge duplicate draft templates" | .mergeStateStatus = "UNKNOWN"
			| .latestOpinionatedReviews.nodes = [{author: {login: $me}, state: "CHANGES_REQUESTED", commit: {oid: $head}}]')" \
		"$(pr_node 106 '.mergeStateStatus = "UNSTABLE" | rollup("FAILURE"; [check("optional-lint"; "FAILURE"; 7001)])
			| .reviewThreads.nodes = [thread(false; "sam-second"; "COMMENTED")]')"
	serve_runs "$HEAD" '[workflow_run(7001; 11; "pull_request")]'

	run_queue

	[ "$status" -eq 0 ]
	assert_json '[.prs[].readiness | [.verdict, .blockers]] | unique' '[["check",[]]]'
	assert_json '[.prs[].readiness.cautions]' '[["CI running"],["2 unresolved threads from others"],["stacked on #99"],["no CI checks","no description"],["merge state unknown"],["a check that is not required is failing","1 unresolved thread from others"]]'
}

@test "a failing check counts against readiness only when branch protection requires it" {
	serve_search open \
		"$(pr_node 101 'rollup("FAILURE"; [check("test"; "SUCCESS"; 7001), check("optional-lint"; "FAILURE"; 7001)])')" \
		"$(pr_node 102 'rollup("FAILURE"; [check("test"; "FAILURE"; 7001), check("optional-lint"; "FAILURE"; 7001)])')" \
		"$(pr_node 103 'rollup("FAILURE"; [check("optional-lint"; "FAILURE"; 7001)])')" \
		"$(pr_node 104 'rollup("FAILURE"; [check("optional-lint"; "FAILURE"; 7001)])')"
	serve_runs "$HEAD" '[workflow_run(7001; 11; "pull_request")]'
	serve_required "acme/widgets#101" test
	serve_required "acme/widgets#102" test
	serve_required "acme/widgets#103"

	run_queue

	[ "$status" -eq 0 ]
	grep -qx 'required acme/widgets#101' "$GH_LOG"
	# GitHub reports BLOCKED while your approval is missing, whichever checks fail.
	assert_json '[.prs[].mergeStateStatus] | unique' '["BLOCKED"]'
	assert_json '.prs[0].readiness' '{"verdict":"check","blockers":[],"cautions":["a check that is not required is failing"]}'
	assert_json '.prs[1].readiness | [.verdict, .blockers]' '["not-ready",["CI failing"]]'
	assert_json '.prs[2].readiness | [.verdict, .blockers, .cautions]' '["check",[],["a check that is not required is failing"]]'
	# Without the required checks, a failing check counts as required unless the PR is UNSTABLE.
	assert_stderr_contains "warning: cannot read the required checks for acme/widgets#104"
	assert_json '.prs[3].readiness | [.verdict, .blockers]' '["not-ready",["CI failing"]]'
}

@test "finds the linked issue in the title, then a Linear link in the description, then the branch name" {
	local link="https://linear.app/acme/issue/WID-42/cache-widget-lookups"
	serve_search open \
		"$(pr_node 101 --arg link "$link" '.body = "Fixes \($link)."')" \
		"$(pr_node 102 --arg link "$link" '.title = "Cache widget lookups in UTF-8" | .headRefName = "ana/wid-7-cache"
			| .body = "Follows https://linear.app/acme/issue/wid-40 and closes [the issue](\($link))."')" \
		"$(pr_node 103 '.title = "Cache widget lookups" | .headRefName = "ana/wid-7-cache-widget-lookups"')" \
		"$(pr_node 104 '.title = "Bump lodash" | .headRefName = "dependabot/npm_and_yarn/lodash-4.17.21"')" \
		"$(pr_node 105 '.title = "Upgrade the runtime" | .headRefName = "ana/upgrade-node-22"')" \
		"$(pr_node 106 '.title = "Bump actions/checkout" | .headRefName = "dependabot/github_actions/actions/checkout-4"')" \
		"$(pr_node 107 '.title = "Update eslint" | .headRefName = "renovate/eslint-9"')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.issue, .issueSource, .issueUrl]' "[\"WID-42\",\"title\",\"$link\"]"
	# A title key wins even when it is a lookalike, so the key stays a candidate.
	assert_json '.prs[1] | [.issue, .issueSource, .issueUrl]' '["UTF-8","title",null]'
	assert_json '.prs[2] | [.issue, .issueSource, .issueUrl]' '["WID-7","branch",null]'
	# A dependency bot's branch names a package and version, never an issue.
	assert_json '[.prs[3, 4, 5, 6] | [.issue, .issueSource, .issueUrl]]' '[[null,null,null],[null,null,null],[null,null,null],[null,null,null]]'
}

@test "takes the issue from the description when the title names none: a Linear link first, then a key after a linking word" {
	serve_search open \
		"$(pr_node 101 '.title = "Cache widget lookups" | .headRefName = "ana/wid-7-cache"
			| .body = "Fixes WID-9. See https://linear.app/acme/issue/wid-40 and https://linear.app/acme/issue/WID-42/cache-widget-lookups."')" \
		"$(pr_node 102 '.title = "Cache widget lookups" | .headRefName = "ana/wid-7-cache"
			| .body = "Reads lookups as UTF-8 and adds SHA-256 sums.\n\nPart of: WID-9"')" \
		"$(pr_node 103 '.title = "Cache widget lookups" | .body = "Reads lookups as UTF-8. fixes #12, fixes utf-8 decoding."')"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [.issue, .issueSource, .issueUrl]' '["WID-40","description","https://linear.app/acme/issue/wid-40"]'
	assert_json '.prs[1] | [.issue, .issueSource, .issueUrl]' '["WID-9","description",null]'
	assert_json '.prs[2] | [.issue, .issueSource, .issueUrl]' '[null,null,null]'
}

@test "gives each PR the command that starts a review of it, for Claude Code and for Codex" {
	serve_search open "$(pr_node 101)"
	# The commands name this skill, so they must change with it.
	grep -qx 'name: pr:github-review' "$BATS_TEST_DIRNAME/../skills/pr:github-review/SKILL.md"
	grep -qx 'user-invocable: true' "$BATS_TEST_DIRNAME/../skills/pr:github-review/SKILL.md"

	run_queue

	[ "$status" -eq 0 ]
	assert_json '.prs[0].reviewCommand.claude' '/trackbed:pr-github-review https://github.com/acme/widgets/pull/101'
	assert_json '.prs[0].reviewCommand.codex' '$trackbed:pr:github-review https://github.com/acme/widgets/pull/101'
	assert_json '.prs[0].reviewCommand | keys' '["claude","codex"]'
}

@test "stays portable to the Bash 3.2 that macOS ships" {
	# Every test runs the script through /bin/bash, so on macOS the whole suite
	# exercises Bash 3.2. These checks also hold the line where /bin/bash is newer.
	if [ "$(uname -s)" = Darwin ]; then
		/bin/bash -c '[ "${BASH_VERSINFO[0]}" -eq 3 ]'
	fi
	local code
	code=$(grep -v '^[[:space:]]*#' "$SCRIPT")
	[ -z "$(grep -wE 'mapfile|readarray' <<<"$code")" ]
	# Under set -u, Bash before 4.4 rejects an empty "${name[@]}", so every array
	# expansion must use the guarded ${name[@]+"${name[@]}"} form.
	[ -z "$(sed -E 's/\$\{[A-Za-z_]+\[@\]\+"\$\{[A-Za-z_]+\[@\]\}"\}//g' <<<"$code" | grep -E '\$\{[A-Za-z_]+\[@\]')" ]
}

@test "rejects malformed arguments before calling GitHub" {
	run_queue --since yesterday
	[ "$status" -eq 2 ]
	assert_stderr_contains "--since must be an ISO-8601 date or time"

	run_queue --repo
	[ "$status" -eq 2 ]

	run_queue --repo widgets
	[ "$status" -eq 2 ]

	run_queue widgets#7
	[ "$status" -eq 2 ]

	run_queue --teams
	[ "$status" -eq 2 ]

	run_queue --repo acme/widgets --all-repos
	[ "$status" -eq 2 ]
	assert_stderr_contains "--repo and --all-repos cannot be combined"

	[ ! -s "$GH_LOG" ]
}

@test "SKILL.md runs the bundled script and stays read-only" {
	grep -Fq 'bash "${CLAUDE_PLUGIN_ROOT}/skills/pr:review-queue/scripts/review-queue.sh"' "$SKILL"
	grep -Fq 'Never submit, approve, or dismiss a review, comment, resolve a thread, re-run a job, update a branch, or merge.' "$SKILL"
	grep -Fq -- '--since <previous checkedAt>' "$SKILL"
	grep -Fq '"Asked to review" means `user-review-requested:@me`.' "$SKILL"
	grep -Fq 'Search every repository only when the user passes `--all-repos`.' "$SKILL"
}

@test "SKILL.md covers a re-request after any earlier review" {
	grep -Fq '| `requestedOfMe`, `myLastReview` set |' "$SKILL"
	grep -Fq 'Re-requested after your <approval / changes request / comment / dismissed review>' "$SKILL"
}

@test "SKILL.md diagnosis commands use quoted variables, not shell-redirect placeholders" {
	grep -Fq 'gh run view "$RUN_ID" -R "$REPO" --log-failed' "$SKILL"
	! grep -Eq '< (run|repo|head) >' "$SKILL" || false
}

@test "SKILL.md report always carries the PR, author, issue, CI, waiting time, and readiness" {
	grep -Fq 'Use these columns in this order, and keep every one in every report' "$SKILL"
	local column
	for column in 'PR' 'Author' 'Linear issue' 'CI' 'Waiting' 'Ready?' 'Your part' 'Workspace'; do
		grep -Fq "| \`$column\` |" "$SKILL"
	done
	grep -Fq 'The number and title, linked to `url`' "$SKILL"
	grep -Fq 'Put the rows in the suggested order below, so the table reads top-down as a work list.' "$SKILL"

	# Every column the report reads comes from a field the script prints.
	serve_search open "$(pr_node 101)"
	run_queue
	[ "$status" -eq 0 ]
	assert_json '.prs[0] | [has("title", "url", "author", "issue", "issueUrl", "ci", "waiting", "waitingFrom", "readiness", "headBranch")] | all' true
}

@test "SKILL.md reads the readiness estimate and lets later steps correct it" {
	grep -Fq '| `ready` | Nothing found in the way | "Yes" |' "$SKILL"
	grep -Fq '| `check` |' "$SKILL"
	grep -Fq '| `not-ready` |' "$SKILL"
	grep -Fq 'When Step 3 finds every failing check a likely flake, read `CI failing` as a caution.' "$SKILL"
	grep -Fq 'A check that has been pending for more than two hours does not count against readiness' "$SKILL"
	grep -Fq '`basePr` is set when the PR'"'"'s base branch is the branch of another open PR.' "$SKILL"
	# The verdicts and reasons the skill names are the ones the script prints.
	grep -Fq '"not-ready"' "$SCRIPT"
	grep -Fq '"check"' "$SCRIPT"
	grep -Fq '"CI failing"' "$SCRIPT"
	grep -Fq '"stacked on #' "$SCRIPT"
	grep -Fq 'def gate_after: 7200;' "$SCRIPT"
}

@test "SKILL.md uses Conductor only when its tools are present, and reads the reference" {
	grep -Fq 'Run this step only when Conductor'"'"'s `ListWorkspaces` and `ListSessions` tools' "$SKILL"
	grep -Fq 'Detect them by presence; never call one to probe.' "$SKILL"
	grep -Fq 'A tool the host lists by name and loads on demand is present: load it.' "$SKILL"
	grep -Fq 'skip Steps 5 and 7, leave the `Workspace` column out of the report, and do not mention Conductor' "$SKILL"
	grep -Fq 'Run this step only when Step 5 ran and Conductor'"'"'s `CreateWorkspace` tool' "$SKILL"
	grep -Fq 'follow its "Find Workspaces and Reviews" section' "$SKILL"
	grep -Fq 'Follow the "Start Reviews" section of `references/conductor.md`' "$SKILL"
	grep -Fxq '## Find Workspaces and Reviews' "$CONDUCTOR"
	grep -Fxq '## Start Reviews' "$CONDUCTOR"
	grep -Fq 'Never message, cancel, or archive a chat or a workspace.' "$SKILL"
	grep -Fq 'never messages, cancels, or archives one' "$CONDUCTOR"
}

@test "the Conductor reference matches PRs to workspaces and review chats without counting passing mentions" {
	grep -Fq 'its `branch` equals the PR'"'"'s `headBranch`, ignoring case' "$CONDUCTOR"
	grep -Fq 'such as `github-review https://github.com/acme/web/pull/`' "$CONDUCTOR"
	grep -Fq 'the match'"'"'s `role` is `user`, so the command was run there.' "$CONDUCTOR"
	grep -Fq 'Assistant text that suggests the command, as an earlier review-queue report does, is not a review.' "$CONDUCTOR"
	grep -Fq 'Any other chat sits in an archived workspace: skip it.' "$CONDUCTOR"
	grep -Fq '`session.id`, to leave this chat out of every result below' "$CONDUCTOR"
	grep -Fq 'List the chats of every matched workspace in one `ListSessions` call with `filter.workspaceIds`' "$CONDUCTOR"
	grep -Fq 'Follow `nextCursor` until it is null, because a search can stop early and return only part of the result.' "$CONDUCTOR"
	grep -Fq 'Search once per repository that has a PR with no workspace yet.' "$CONDUCTOR"
	grep -Fq '| `waiting_for_user` | "Review waiting for your answer". The next move is yours. |' "$CONDUCTOR"
	grep -Fq 'with `ListSessionMessages` and `limit: 5`' "$CONDUCTOR"
}

@test "the Conductor reference starts reviews only after an explicit yes, with the script's unchanged command" {
	grep -Fq 'Nothing here starts without the user'"'"'s explicit yes in this run.' "$CONDUCTOR"
	grep -Fq 'the section above found no workspace and no review chat for it' "$CONDUCTOR"
	grep -Fq 'Lead with the decision and keep the offer to a few lines:' "$CONDUCTOR"
	grep -Fq 'Reply "all", the PR numbers to start, or "none".' "$CONDUCTOR"
	grep -Fq 'its `Ready?` cell says "Yes" or "Probably"' "$CONDUCTOR"
	grep -Fq 'End the report with the offer, then end the turn and wait for the answer.' "$CONDUCTOR"
	grep -Fq 'Treat anything other than a clear yes with a selection as no, and start nothing.' "$CONDUCTOR"
	grep -Fq 'the PR'"'"'s `reviewCommand.claude` or `reviewCommand.codex` from the snapshot' "$CONDUCTOR"
	grep -Fq 'Copy the message exactly. Never compose, edit, or append to it, and never add a flag' "$CONDUCTOR"
	grep -Fq 'call it once more with the same three IDs' "$CONDUCTOR"
	grep -Fq 'Never create a `failed` or `unknown` PR again in this run.' "$CONDUCTOR"
	grep -Fq 'it posts nothing to GitHub without asking you in its own workspace' "$CONDUCTOR"
}
