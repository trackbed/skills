#!/usr/bin/env bats

load 'test_helper/common'

extract_commit_and_include_block() {
	python3 - "$1" "$2" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text()
section = source.split('#### If "Commit and include"', 1)[1]
block = section.split("```bash", 1)[1].split("```", 1)[0].strip()
pathlib.Path(sys.argv[2]).write_text(f"{block}\n")
PY
}

extract_single_commit_fast_path_block() {
	python3 - "$1" "$2" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text()
section = source.split("\n## Single-Commit Fast Path\n", 1)[1].split("\n## ", 1)[0]
block = section.split("```bash", 1)[1].split("```", 1)[0].strip()
pathlib.Path(sys.argv[2]).write_text(f"{block}\n")
PY
}

init_single_commit_fixture() {
	repo="$BATS_TEST_TMPDIR/repo"
	block="$BATS_TEST_TMPDIR/fast-path.sh"
	MESSAGE_FILE="$BATS_TEST_TMPDIR/message.txt"
	extract_single_commit_fast_path_block \
		"$BATS_TEST_DIRNAME/../skills/git:recreate-commits/SKILL.md" "$block"
	init_test_git_repo "$repo"
	cd "$repo"
	RESET_POINT=$(git rev-parse HEAD)
	git checkout -q -b feature
	printf 'Add the feature in one step\n\nExplain why the feature exists.\n' >"$MESSAGE_FILE"
}

file_mode() {
	if [ "$(uname -s)" = "Darwin" ]; then
		stat -f '%Lp' "$1"
	else
		stat -c '%a' "$1"
	fi
}

@test "pr-create owns lease-protected remote publication" {
    cd "$BATS_TEST_DIRNAME/.."
    create="skills/pr:create/SKILL.md"
    branch="skills/pr:create/references/branch-and-platform-handling.md"
    confirmation="skills/pr:create/references/confirmation-and-creation.md"
    recreate="skills/git:recreate-commits/SKILL.md"
    description="skills/pr:generate-description/SKILL.md"

    assert_required_text "$create" "disable-model-invocation: false"
    assert_required_text "$recreate" "disable-model-invocation: false"
    assert_required_text "$description" "disable-model-invocation: false"
    assert_required_text "$recreate" "### Model Invocation Contract"
    assert_required_text "$create" "### Model Invocation Contract"
    assert_required_text "$create" "No other parent workflow is authorized by this model-invocation exception"
    assert_required_text "$recreate" "No other parent workflow is authorized by the model-invocation exception"
    assert_required_text "$recreate" "Outside that exact \`trackbed:pr:create\` delegation, never invent \`--authorize-history-rewrite\`"
    assert_required_text "$recreate" "The model must never invent \`--force-backup\`"
    assert_required_text "$recreate" "only with the exact retry-safe value supplied by \`trackbed:pr:create\`"
    assert_required_text "$description" "Every model-initiated invocation must include \`--no-update\`"
    assert_required_text "$create" "args: \"--base {base-source-ref} --base-commit {base-ref} --backup-ref {recreate-backup-ref} --require-unstacked --no-push\""
    invocation='skill: "trackbed:git:recreate-commits", args:'
    assert_text_count "$create" "$invocation" 5
    assert_text_count "$create" '--base {base-source-ref} --base-commit {base-ref}' 5 "$invocation"
    assert_text_count "$create" '--backup-ref {recreate-backup-ref}' 5 "$invocation"
    assert_text_count "$create" '--require-unstacked --no-push' 5 "$invocation"
    assert_text_count "$create" '--manual ' 2 "$invocation"
    assert_text_count "$create" '--authorize-history-rewrite' 2 "$invocation"
    assert_text_count "$create" '--after {observed-origin-oid}' 1 "$invocation"
    assert_absent_text "$create" "args: \"--no-push\""
    assert_required_text "$create" "Always pass \`--no-update --base {base-source-ref} --base-commit {base-ref}\`, and never \`--manual\`"
    assert_required_text "$branch" "Do not push or change upstream configuration"
    assert_absent_text "$branch" "git push -u origin \$(git branch --show-current)"
    assert_text_count "$confirmation" 'FINAL_STACK_RESOLVED=' 3
    assert_text_order "$confirmation" 'FINAL_STACK_RESOLVED=' 'git push --no-follow-tags'
    assert_text_order "$confirmation" 'FINAL_STACK_RESOLVED=' 'git push --force-with-lease="{rollback-origin-ref}:"' 2
    assert_text_order "$confirmation" 'FINAL_STACK_RESOLVED=' 'env GH_PROMPT_DISABLED=1 gh pr create' 3
    assert_required_text "$confirmation" "[ \"\$STACK_MEMBERSHIP\" = none ]"
    assert_required_text "$confirmation" "The branch joined a local or server-side stack before the fast-forward push"
    assert_required_text "$confirmation" "The branch joined a local or server-side stack before the fresh push"
    assert_required_text "$confirmation" "The branch joined a local or server-side stack before Pull Request creation"
    assert_required_text "$confirmation" "If an open Pull Request appeared after Step 3.5"
    assert_required_text "$confirmation" "--force-with-lease=\"refs/heads/{feature-branch}:{observed-origin-oid}\""
    assert_required_text "$confirmation" "--no-follow-tags"
    assert_required_text "$confirmation" "-- \"\$ORIGIN_PUSH_URL\" \"{publication-commit}:refs/heads/{feature-branch}\""
    assert_required_text "$confirmation" "{origin-push-url-assignment}"
    assert_absent_text "$confirmation" "\"{origin-push-url}\""
    assert_absent_text "$confirmation" "-u origin \"HEAD:refs/heads/{feature-branch}\""
    assert_required_text "$confirmation" "authentication failure is a hard blocker, never a reason to wait for terminal input"
    assert_absent_text "$confirmation" "--force-with-lease=\"{rollback-origin-ref}:{rollback-origin-oid}\""
    assert_required_text "$confirmation" "The exact lease rejects every remote change after classification"
    assert_required_text "$confirmation" "The immediately preceding strict-ancestor proof ensures this invocation cannot use the force capability to replace remote-only work"
    assert_required_text "$recreate" "[--require-unstacked] [--no-push] [--authorize-history-rewrite]"
    assert_required_text "$recreate" "If \`--no-push\` was passed, do not run any push command"
    assert_required_text docs/shipping.md "Automatic stack-wide rewriting additionally requires \`--authorize-history-rewrite\`"
    assert_required_text docs/shipping.md "A \`--manual\` stacked invocation may instead use separate interactive confirmations"
    assert_required_text "$create" "\${CLAUDE_PLUGIN_ROOT}/scripts/resolve-stack-membership.sh"
    assert_required_text "$create" "trackbed:pr:create does not publish stacked branches; use trackbed:pr:stack instead."
    assert_absent_text "$create" "leaves any stacked rewrite to the nested skill"
    assert_absent_text "$recreate" "\`--auto\` alone is not authorization"

	assert_required_contracts_registered \
		pr-create-description-generation-contract \
		pr-create-history-rewrite-authorization \
		pr-create-stack-publication-boundary \
		pr-create-deferred-upstream-contract \
		pr-create-absence-lease-contract \
		pr-create-origin-push-url-helper \
		pr-create-push-failure-rollback \
		pr-create-remote-absence-contract \
		pr-create-preflight-helper \
		recreate-commits-deferred-push-contract \
		pr-generate-description-subskill-contract \
		recreate-commits-push-target-helper \
		recreate-commits-retry-safe-backup \
		resolve-base-pinned-commit-contract \
		verify-rewrite-state-helper

}

@test "recreate-commits auto mode stays within the protected unstacked boundary" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    recreate="skills/git:recreate-commits/SKILL.md"

    grep -qF "If \`IN_STACK=true\` and neither \`--manual\` nor \`--authorize-history-rewrite\` was passed, stop before the reset" "$recreate"
    grep -qF "When \`REQUIRE_UNSTACKED=true\` and \`--no-push\` was passed (the \`trackbed:pr:create\` delegation), skip this initial resolution and set \`IN_STACK=false\`" "$recreate"
    grep -qF "Under \`REQUIRE_UNSTACKED=true\`, any local or server-side membership is state drift" "$recreate"
    grep -qF "stop before the reset, even in auto mode or when \`--authorize-history-rewrite\` was passed" "$recreate"
    grep -qF "Do not reinterpret an unstacked-only parent authorization as approval to rewrite or restack multiple branches" "$recreate"
    grep -qF "The branch joined a local or server-side stack after initial validation; stop before rewriting history." "$recreate"
    grep -qF "Run the stack-revalidation block above only when the parsed agent state has \`REQUIRE_UNSTACKED=true\`" "$recreate"
    grep -qF "Do not wrap it in a shell-local \`REQUIRE_UNSTACKED\` conditional" "$recreate"
    ! grep -qF "\${REQUIRE_UNSTACKED:-false}" "$recreate" || false
    latest_stack_line=$(grep -nF "LATEST_STACK_RESOLVED=" "$recreate" | tail -1 | cut -d: -f1)
    reset_line=$(grep -nF "git reset --hard \"\$RESET_POINT\"" "$recreate" | head -1 | cut -d: -f1)
    [ "$latest_stack_line" -lt "$reset_line" ]
    grep -qF '/skills/git:recreate-commits/scripts/stack-branch-names.sh' "$recreate"
    grep -qF "require its output to equal \`STACK_BRANCH_NAMES\` byte-for-byte" "$recreate"
    grep -qF "enumerate every branch in \`STACK_BRANCHES\`" "$recreate"
    grep -qF "explicit confirmation authorizing both the reset and that restack" "$recreate"
    grep -qF "explicit confirmation authorizing that whole-stack push" "$recreate"
    grep -qF "A reset/restack confirmation does not also authorize publication" "$recreate"
    grep -qF -- "--base-branch \"\$BASE_BRANCH\"" "$recreate"
    grep -qF "[ \"\$(git symbolic-ref --quiet --short HEAD)\" = \"\$ORIGINAL_BRANCH\" ]" "$recreate"
    grep -qF "verify-rewrite-state.sh" "$recreate"
    publication="skills/pr:create/references/confirmation-and-creation.md"
    grep -qF "Do not publish or create a default-base Pull Request from stale unstacked authorization." "$publication"
    authorization_line=$(grep -nF "Do not publish or create a default-base Pull Request from stale unstacked authorization." "$publication" | cut -d: -f1)
    first_guard_line=$(grep -nF "FINAL_STACK_RESOLVED=" "$publication" | head -1 | cut -d: -f1)
    [ "$authorization_line" -lt "$first_guard_line" ]
    grep -qF "The current branch changed after push-target resolution; stop before pushing." "$recreate"
    grep -qF "without the captured ref-specific \`--force-with-lease\`" "$recreate"
    grep -qF -- "--no-follow-tags" "$recreate"
    grep -qF -- "--force-with-lease=\"\${PUSH_REMOTE_REF}:\${PUSH_LEASE_OID}\"" "$recreate"
    grep -qF -- "-- \"\$PUSH_REMOTE_URL\" \"HEAD:\${PUSH_REMOTE_REF}\"" "$recreate"
    ! grep -qF "push with \`git push --force-with-lease\`" "$recreate" || false
    ! grep -qF "\`--auto\` alone is not authorization" "$recreate" || false
	'

	[ "$status" -eq 0 ]
}

@test "recreate-commits coarse mode selects first-pass granularity without widening authorization" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    recreate="skills/git:recreate-commits/SKILL.md"

    grep -qF "[--manual] [--coarse|--granular]" "$recreate"
    grep -qF -- "\`--coarse\` — Force coarse decomposition: one commit per major grouping" "$recreate"
    grep -qF "auto mode keeps authorizing them, and \`--manual\` keeps their confirmations" "$recreate"
    grep -qF "does not authorize the history rewrite or publication by itself" "$recreate"
    grep -qF "a positional token, or \`--coarse\` combined with \`--granular\`" "$recreate"
    grep -qF "\`--coarse\` selects **Coarse** granularity unconditionally and skips the granularity question" "$recreate"
    grep -qF "In auto mode, either fixed-granularity flag replaces automatic granularity selection and every other auto-mode behavior remains in effect" "$recreate"
    grep -qF "For **coarse** granularity, stop here — each grouping becomes one commit" "$recreate"
    grep -qF "Before resetting, unless \`--authorize-history-rewrite\` was passed or (auto mode is active and \`IN_STACK=false\`), obtain the applicable confirmation" "$recreate"
    grep -qF "Before pushing, unless \`--authorize-history-rewrite\` was passed or (auto mode is active and \`IN_STACK=false\`), obtain the applicable publication confirmation" "$recreate"
    grep -qF "[--manual] [--coarse\\|--granular]" ../README.md
	  '

	[ "$status" -eq 0 ]
}

@test "recreate-commits single-commit fast path runs only after every pre-reset gate" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    recreate="skills/git:recreate-commits/SKILL.md"

    [ "$(grep -c "^## Single-Commit Fast Path$" "$recreate")" -eq 1 ]
    grep -qF "If the Step 4 storyline is exactly one commit and no \`{branch_name}-clean\` branch is in use, follow \`## Single-Commit Fast Path\` instead of the reset and rebuild bullets below, then continue with Step 6." "$recreate"
    heading_line=$(grep -n "^## Single-Commit Fast Path$" "$recreate" | cut -d: -f1)
    routing_line=$(grep -nF "follow \`## Single-Commit Fast Path\`" "$recreate" | cut -d: -f1)
    latest_stack_line=$(grep -nF "LATEST_STACK_RESOLVED=" "$recreate" | tail -1 | cut -d: -f1)
    verify_line=$(grep -nF "scripts/verify-rewrite-state.sh\" \\" "$recreate" | tail -1 | cut -d: -f1)
    reset_line=$(grep -nF "git reset --hard \"\$RESET_POINT\"" "$recreate" | head -1 | cut -d: -f1)
    [ "$latest_stack_line" -lt "$routing_line" ]
    [ "$verify_line" -lt "$routing_line" ]
    [ "$routing_line" -lt "$reset_line" ]
    [ "$latest_stack_line" -lt "$heading_line" ]
    [ "$verify_line" -lt "$heading_line" ]

    section=$(awk "/^## Single-Commit Fast Path\$/{found=1; next} found && /^## /{exit} found" "$recreate")
    grep -qF "git commit --amend --file=\"\$MESSAGE_FILE\"" <<<"$section"
    grep -qF "git reset --soft \"\$RESET_POINT\"" <<<"$section"
    grep -qF "git rev-list --no-merges --count" <<<"$section"
    grep -qF "HEAD moved after revalidation; stop before rewording." <<<"$section"
    grep -qF "git diff \"\$ORIGINAL_TIP\" HEAD" <<<"$section"
    grep -qF "git reset --hard \"\$BACKUP_REF\"" <<<"$section"
    grep -qF "Never move or delete \`BACKUP_REF\`" <<<"$section"
    grep -qF "never with a \`{branch_name}-clean\` branch" <<<"$section"
    grep -qF "has already run before this point" <<<"$section"
    ! grep -qF "git push" <<<"$section" || false
    ! grep -qF "git reset --hard \"\$RESET_POINT\"" <<<"$section" || false
	'

	[ "$status" -eq 0 ]
}

@test "recreate-commits fast path rewords one commit in place and keeps its author and tree" {
	init_single_commit_fixture
	printf 'feature\n' >feature.txt
	git add feature.txt
	GIT_AUTHOR_NAME="Original Author" GIT_AUTHOR_EMAIL="original@example.com" \
		git commit -q -m "Include uncommitted changes for PR creation"
	ORIGINAL_TIP=$(git rev-parse HEAD)
	git branch feature-recreate-backup "$ORIGINAL_TIP"

	ORIGINAL_TIP="$ORIGINAL_TIP" RESET_POINT="$RESET_POINT" MESSAGE_FILE="$MESSAGE_FILE" \
		run bash "$block"
	[ "$status" -eq 0 ]

	[ "$(git rev-parse HEAD^)" = "$RESET_POINT" ]
	[ "$(git rev-list --count "$RESET_POINT..HEAD")" -eq 1 ]
	[ -z "$(git diff "$ORIGINAL_TIP" HEAD)" ]
	[ "$(git log -1 --format='%an <%ae>')" = "Original Author <original@example.com>" ]
	[ "$(git log -1 --format='%s')" = "Add the feature in one step" ]
	[ "$(git rev-parse feature-recreate-backup)" = "$ORIGINAL_TIP" ]
	[ "$(git symbolic-ref --short HEAD)" = "feature" ]
}

@test "recreate-commits fast path squashes a range containing a merge into one commit" {
	init_single_commit_fixture
	printf 'one\n' >one.txt
	git add one.txt
	git commit -q -m "First feature step"
	git checkout -q -b side "$RESET_POINT"
	printf 'side\n' >side.txt
	git add side.txt
	git commit -q -m "Side work"
	git checkout -q feature
	git merge -q --no-ff --no-edit side
	ORIGINAL_TIP=$(git rev-parse HEAD)
	git branch feature-recreate-backup "$ORIGINAL_TIP"
	[ "$(git rev-list --count "$RESET_POINT..HEAD")" -eq 3 ]

	ORIGINAL_TIP="$ORIGINAL_TIP" RESET_POINT="$RESET_POINT" MESSAGE_FILE="$MESSAGE_FILE" \
		run bash "$block"
	[ "$status" -eq 0 ]

	[ "$(git rev-list --count "$RESET_POINT..HEAD")" -eq 1 ]
	[ "$(git rev-list --parents -n 1 HEAD | wc -w | tr -d ' ')" -eq 2 ]
	[ "$(git rev-parse HEAD^)" = "$RESET_POINT" ]
	[ "$(git rev-parse 'HEAD^{tree}')" = "$(git rev-parse "$ORIGINAL_TIP^{tree}")" ]
	[ -z "$(git diff "$ORIGINAL_TIP" HEAD)" ]
	[ "$(git log -1 --format='%s')" = "Add the feature in one step" ]
	[ "$(git rev-parse feature-recreate-backup)" = "$ORIGINAL_TIP" ]
}

@test "recreate-commits fast path refuses when HEAD moved after revalidation" {
	init_single_commit_fixture
	printf 'feature\n' >feature.txt
	git add feature.txt
	git commit -q -m "Include uncommitted changes for PR creation"
	ORIGINAL_TIP=$(git rev-parse HEAD)
	printf 'later\n' >later.txt
	git add later.txt
	git commit -q -m "Concurrent work"
	moved_head=$(git rev-parse HEAD)

	ORIGINAL_TIP="$ORIGINAL_TIP" RESET_POINT="$RESET_POINT" MESSAGE_FILE="$MESSAGE_FILE" \
		run bash "$block"
	[ "$status" -ne 0 ]
	[[ "$output" == *"HEAD moved after revalidation; stop before rewording."* ]] || false
	[ "$(git rev-parse HEAD)" = "$moved_head" ]
	[ "$(git log -1 --format='%s')" = "Concurrent work" ]
}

@test "absence lease rejects a concurrently created remote branch" {
	run bash -c '
    set -e
    root="$1"
    remote="$root/remote.git"
    publisher="$root/publisher"
    contender="$root/contender"

    git init --bare "$remote" >/dev/null
    git init "$publisher" >/dev/null
    git -C "$publisher" config user.name "Test User"
    git -C "$publisher" config user.email "test@example.com"
    printf "base\n" >"$publisher/file.txt"
    git -C "$publisher" add file.txt
    git -C "$publisher" commit -m "base" >/dev/null
    git -C "$publisher" branch -M main
    git -C "$publisher" remote add origin "$remote"
    git -C "$publisher" push -u origin main >/dev/null
    git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

    git clone "$remote" "$contender" >/dev/null
    git -C "$publisher" checkout -b feature >/dev/null
    printf "publisher\n" >>"$publisher/file.txt"
    git -C "$publisher" commit -am "publisher work" >/dev/null

    test -z "$(git -C "$publisher" ls-remote --heads origin refs/heads/feature)"
    git -C "$contender" checkout -b feature origin/main >/dev/null
    git -C "$contender" push origin HEAD:refs/heads/feature >/dev/null
    expected=$(git -C "$contender" rev-parse HEAD)

    if "${CONDUCTOR_REAL_GIT_PATH:-git}" -C "$publisher" push \
      --force-with-lease=refs/heads/feature: \
      origin HEAD:refs/heads/feature >/dev/null 2>&1; then
      exit 1
    fi

    actual=$(git -C "$publisher" ls-remote --heads origin refs/heads/feature | awk "{print \$1}")
    test "$actual" = "$expected"
  ' _ "$BATS_TEST_TMPDIR"

	[ "$status" -eq 0 ]
}

@test "OID lease publishes the immutable strict fast-forward without widening or retargeting" {
	remote="$BATS_TEST_TMPDIR/remote.git"
	publisher="$BATS_TEST_TMPDIR/publisher"
	resolver="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/resolve-origin-push-url.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file file.txt
	git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

	git -C "$publisher" checkout -b feature >/dev/null
	printf "published\n" >>"$publisher/file.txt"
	git -C "$publisher" commit -am "published work" >/dev/null
	git -C "$publisher" push -u origin feature >/dev/null
	observed=$(git -C "$publisher" rev-parse HEAD)

	printf "local one\n" >>"$publisher/file.txt"
	git -C "$publisher" commit -am "local work one" >/dev/null
	printf "local two\n" >>"$publisher/file.txt"
	git -C "$publisher" commit -am "local work two" >/dev/null
	entry_commit=$(git -C "$publisher" rev-parse HEAD)
	upstream_remote=$(git -C "$publisher" config --get branch.feature.remote)
	upstream_merge=$(git -C "$publisher" config --get branch.feature.merge)

	git -C "$publisher" merge-base --is-ancestor "$observed" "$entry_commit"
	git -C "$publisher" tag -a release-candidate "$entry_commit" -m "release candidate"
	git -C "$publisher" config push.followTags true
	printf "late local change\n" >>"$publisher/file.txt"
	git -C "$publisher" commit -am "late local work" >/dev/null
	live_head=$(git -C "$publisher" rev-parse HEAD)
	[ "$live_head" != "$entry_commit" ]

	cd "$publisher"
	run "$resolver"
	[ "$status" -eq 0 ]
	eval "$output"
	[ "$ORIGIN_PUSH_URL" = "$remote" ]

	run "${CONDUCTOR_REAL_GIT_PATH:-git}" push \
		--no-follow-tags \
		--force-with-lease=refs/heads/feature:"$observed" \
		-- "$ORIGIN_PUSH_URL" "$entry_commit:refs/heads/feature"
	[ "$status" -eq 0 ]

	remote_head=$(git ls-remote --heads -- "$ORIGIN_PUSH_URL" refs/heads/feature | awk '{print $1}')
	[ "$remote_head" = "$entry_commit" ]
	[ "$(git rev-parse HEAD)" = "$live_head" ]
	[ "$(git config --get branch.feature.remote)" = "$upstream_remote" ]
	[ "$(git config --get branch.feature.merge)" = "$upstream_merge" ]
	! git --git-dir="$remote" show-ref --verify --quiet refs/tags/release-candidate || false
}

@test "OID lease rejects a remote change after fast-forward classification" {
	remote="$BATS_TEST_TMPDIR/remote.git"
	publisher="$BATS_TEST_TMPDIR/publisher"
	contender="$BATS_TEST_TMPDIR/contender"
	init_test_git_repo "$publisher" --origin "$remote" --file file.txt
	git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

	git -C "$publisher" checkout -b feature >/dev/null
	printf "published\n" >>"$publisher/file.txt"
	git -C "$publisher" commit -am "published work" >/dev/null
	git -C "$publisher" push -u origin feature >/dev/null
	observed=$(git -C "$publisher" rev-parse HEAD)

	git clone "$remote" "$contender" >/dev/null
	git -C "$contender" config user.name "Other User"
	git -C "$contender" config user.email "other@example.com"
	git -C "$contender" config commit.gpgsign false
	git -C "$contender" checkout feature >/dev/null

	printf "local\n" >>"$publisher/file.txt"
	git -C "$publisher" commit -am "local work" >/dev/null
	entry_commit=$(git -C "$publisher" rev-parse HEAD)
	git -C "$publisher" merge-base --is-ancestor "$observed" "$entry_commit"

	printf "remote\n" >>"$contender/file.txt"
	git -C "$contender" commit -am "remote work" >/dev/null
	git -C "$contender" push origin HEAD:refs/heads/feature >/dev/null
	contender_head=$(git -C "$contender" rev-parse HEAD)

	run "${CONDUCTOR_REAL_GIT_PATH:-git}" -C "$publisher" push \
		--no-follow-tags \
		--force-with-lease=refs/heads/feature:"$observed" \
		-- "$remote" "$entry_commit:refs/heads/feature"
	[ "$status" -ne 0 ]

	remote_head=$(git -C "$publisher" ls-remote --heads -- "$remote" refs/heads/feature | awk '{print $1}')
	[ "$remote_head" = "$contender_head" ]
	[ "$remote_head" != "$entry_commit" ]
}

@test "serialized push URL remains inert across shell invocations" {
	remote="$BATS_TEST_TMPDIR/remote-\$(touch injected-by-url).git"
	publisher="$BATS_TEST_TMPDIR/publisher"
	resolver="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/resolve-origin-push-url.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file file.txt
	git --git-dir="$remote" symbolic-ref HEAD refs/heads/main

	cd "$publisher"
	run "$resolver"
	[ "$status" -eq 0 ]
	assignment="$output"
	[[ "$assignment" == ORIGIN_PUSH_URL=* ]] || false

	run bash -c '
    set -e
    assignment=$1
    eval "$assignment"
    git ls-remote --heads -- "$ORIGIN_PUSH_URL" refs/heads/main
  ' _ "$assignment"

	[ "$status" -eq 0 ]
	[ ! -e "$publisher/injected-by-url" ]
}

@test "origin push URL resolver rejects inline credentials without echoing them" {
	remote="$BATS_TEST_TMPDIR/remote.git"
	publisher="$BATS_TEST_TMPDIR/publisher"
	resolver="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/resolve-origin-push-url.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file file.txt
	git -C "$publisher" remote set-url --push origin "https://oauth2:secret-token@example.invalid/repo.git"

	cd "$publisher"
	run "$resolver"

	[ "$status" -ne 0 ]
	[[ "$output" == *"must not contain inline HTTP credentials"* ]] || false
	[[ "$output" != *"secret-token"* ]] || false
}

@test "origin push URL resolver rejects executable and unknown transports" {
	remote="$BATS_TEST_TMPDIR/remote.git"
	publisher="$BATS_TEST_TMPDIR/publisher"
	resolver="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/resolve-origin-push-url.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file file.txt

	for push_url in "ext::sh -c touch% payload-marker" "custom-helper::payload-marker" "custom://payload-marker"; do
		git -C "$publisher" remote set-url --push origin "$push_url"
		cd "$publisher"
		run "$resolver"

		[ "$status" -ne 0 ]
		[[ "$output" == *"executable Git remote-helper syntax"* || "$output" == *"unsupported transport"* ]] || false
		[[ "$output" != *"payload-marker"* ]] || false
	done
}

@test "dirty append preserves the published prefix for exact and ancestor tips" {
	resolver="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/resolve-origin-push-url.sh"

	for mode in exact ancestor; do
		remote="$BATS_TEST_TMPDIR/$mode-remote.git"
		publisher="$BATS_TEST_TMPDIR/$mode-publisher"
		init_test_git_repo "$publisher" --origin "$remote" --file tracked.txt
		git --git-dir="$remote" symbolic-ref HEAD refs/heads/main
		git -C "$publisher" checkout -b feature >/dev/null
		printf 'published\n' >>"$publisher/tracked.txt"
		git -C "$publisher" commit -am "published prefix" >/dev/null
		git -C "$publisher" push -u origin feature >/dev/null
		observed=$(git -C "$publisher" rev-parse HEAD)

		if [ "$mode" = ancestor ]; then
			printf 'unpublished\n' >>"$publisher/tracked.txt"
			git -C "$publisher" commit -am "unpublished local work" >/dev/null
		fi
		entry_commit=$(git -C "$publisher" rev-parse HEAD)
		printf 'staged\n' >"$publisher/staged.txt"
		git -C "$publisher" add staged.txt
		printf 'unstaged\n' >>"$publisher/tracked.txt"
		printf 'untracked\n' >"$publisher/untracked.txt"
		git -C "$publisher" add -A
		git -C "$publisher" commit -m "include dirty work" >/dev/null
		include_commit=$(git -C "$publisher" rev-parse HEAD)

		git -C "$publisher" reset --soft "$observed"
		git -C "$publisher" commit -m "narrative append" >/dev/null
		publication_commit=$(git -C "$publisher" rev-parse HEAD)
		git -C "$publisher" diff --quiet "$include_commit" "$publication_commit"
		[ "$(git -C "$publisher" rev-parse "$publication_commit^")" = "$observed" ]
		git -C "$publisher" merge-base --is-ancestor "$observed" "$publication_commit"

		cd "$publisher"
		run "$resolver"
		[ "$status" -eq 0 ]
		eval "$output"
		run git push --no-follow-tags \
			--force-with-lease=refs/heads/feature:"$observed" \
			-- "$ORIGIN_PUSH_URL" "$publication_commit:refs/heads/feature"
		[ "$status" -eq 0 ]

		remote_head=$(git ls-remote --heads -- "$ORIGIN_PUSH_URL" refs/heads/feature | awk '{print $1}')
		[ "$remote_head" = "$publication_commit" ]
		[ "$(git show "$remote_head:staged.txt")" = staged ]
		[ "$(git show "$remote_head:untracked.txt")" = untracked ]
		[[ "$(git show "$remote_head:tracked.txt")" == *unstaged* ]] || false
		if [ "$mode" = exact ]; then
			[ "$entry_commit" = "$observed" ]
		else
			[ "$entry_commit" != "$observed" ]
			[[ "$(git show "$remote_head:tracked.txt")" == *unpublished* ]] || false
		fi
	done
}

@test "dirty append can safely restore its pre-publication state" {
	remote="$BATS_TEST_TMPDIR/rollback-remote.git"
	publisher="$BATS_TEST_TMPDIR/rollback-publisher"
	clean_check="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file tracked.txt
	git --git-dir="$remote" symbolic-ref HEAD refs/heads/main
	git -C "$publisher" checkout -b feature >/dev/null
	printf 'published\n' >>"$publisher/tracked.txt"
	git -C "$publisher" commit -am "published prefix" >/dev/null
	git -C "$publisher" push -u origin feature >/dev/null
	original_commit=$(git -C "$publisher" rev-parse HEAD)

	printf 'dirty tracked\n' >>"$publisher/tracked.txt"
	printf 'dirty untracked\n' >"$publisher/untracked.txt"
	git -C "$publisher" add -A
	git -C "$publisher" commit -m "include dirty work" >/dev/null
	include_commit=$(git -C "$publisher" rev-parse HEAD)
	git -C "$publisher" reset --soft "$original_commit"
	git -C "$publisher" commit -m "narrative append" >/dev/null
	publication_commit=$(git -C "$publisher" rev-parse HEAD)

	cd "$publisher"
	run "$clean_check"
	[ "$status" -eq 0 ]
	[ "$(git -C "$publisher" branch --show-current)" = feature ]
	[ "$(git -C "$publisher" rev-parse HEAD)" = "$publication_commit" ]
	git -C "$publisher" reset --keep "$original_commit" >/dev/null
	git -C "$publisher" cherry-pick --no-commit "$include_commit" >/dev/null
	git -C "$publisher" reset >/dev/null

	[ "$(git -C "$publisher" rev-parse HEAD)" = "$original_commit" ]
	[ "$(git -C "$publisher" ls-remote --heads origin refs/heads/feature | awk '{print $1}')" = "$original_commit" ]
	[[ "$(git -C "$publisher" status --porcelain)" == *" M tracked.txt"* ]] || false
	[[ "$(git -C "$publisher" status --porcelain)" == *"?? untracked.txt"* ]] || false
	[[ "$(cat "$publisher/tracked.txt")" == *"dirty tracked"* ]] || false
	[ "$(cat "$publisher/untracked.txt")" = "dirty untracked" ]
}

@test "dirty append can restore a safe pre-recreation input after child failure" {
	remote="$BATS_TEST_TMPDIR/pre-recreation-remote.git"
	publisher="$BATS_TEST_TMPDIR/pre-recreation-publisher"
	clean_check="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file tracked.txt
	git --git-dir="$remote" symbolic-ref HEAD refs/heads/main
	git -C "$publisher" checkout -b feature >/dev/null
	printf 'published\n' >>"$publisher/tracked.txt"
	git -C "$publisher" commit -am "published prefix" >/dev/null
	git -C "$publisher" push -u origin feature >/dev/null
	original_commit=$(git -C "$publisher" rev-parse HEAD)

	printf 'dirty tracked\n' >>"$publisher/tracked.txt"
	printf 'dirty untracked\n' >"$publisher/untracked.txt"
	git -C "$publisher" add -A
	git -C "$publisher" commit -m "include dirty work" >/dev/null
	include_commit=$(git -C "$publisher" rev-parse HEAD)
	recreate_input_tip=$include_commit

	cd "$publisher"
	run "$clean_check"
	[ "$status" -eq 0 ]
	[ "$(git branch --show-current)" = feature ]
	[ "$(git rev-parse HEAD)" = "$recreate_input_tip" ]

	git reset --keep "$original_commit" >/dev/null
	git cherry-pick --no-commit "$include_commit" >/dev/null
	git reset >/dev/null

	[ "$(git rev-parse HEAD)" = "$original_commit" ]
	[[ "$(git status --porcelain)" == *" M tracked.txt"* ]] || false
	[[ "$(git status --porcelain)" == *"?? untracked.txt"* ]] || false
}

@test "dirty append rollback refuses work added after its final guard" {
	repo="$BATS_TEST_TMPDIR/rollback-drift-repo"
	clean_check="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	init_test_git_repo "$repo" --file tracked.txt
	original_commit=$(git -C "$repo" rev-parse HEAD)

	printf 'prepared\n' >"$repo/tracked.txt"
	git -C "$repo" commit -am "prepared append" >/dev/null
	prepared_commit=$(git -C "$repo" rev-parse HEAD)

	cd "$repo"
	run "$clean_check"
	[ "$status" -eq 0 ]
	[ "$(git rev-parse HEAD)" = "$prepared_commit" ]

	printf 'parallel work\n' >tracked.txt
	run git reset --keep "$original_commit"

	[ "$status" -ne 0 ]
	[ "$(git rev-parse HEAD)" = "$prepared_commit" ]
	[ "$(cat tracked.txt)" = "parallel work" ]
}

@test "origin push URL resolver rejects multiple publication endpoints" {
	remote="$BATS_TEST_TMPDIR/remote.git"
	mirror="$BATS_TEST_TMPDIR/mirror.git"
	publisher="$BATS_TEST_TMPDIR/publisher"
	resolver="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/resolve-origin-push-url.sh"
	init_test_git_repo "$publisher" --origin "$remote" --file file.txt
	git clone --bare "$remote" "$mirror" >/dev/null
	git -C "$publisher" remote set-url --push origin "$remote"
	git -C "$publisher" remote set-url --add --push origin "$mirror"

	cd "$publisher"
	run "$resolver"

	[ "$status" -ne 0 ]
	[[ "$output" == *"must resolve to exactly one push URL"* ]] || false
}

@test "existing remote branch recovers at exact tip or safely fast-forwards from an ancestor" {
    cd "$BATS_TEST_DIRNAME/.."
    create="skills/pr:create/SKILL.md"
    branch="skills/pr:create/references/branch-and-platform-handling.md"
    state="skills/pr:create/references/state-and-rollback.md"
    confirmation="skills/pr:create/references/confirmation-and-creation.md"

    assert_required_text "$create" "REMOTE_RECOVERY_MODE=true"
    assert_required_text "$create" "REMOTE_FAST_FORWARD_MODE=true"
    assert_required_text "$create" "REMOTE_APPEND_MODE=true"
    assert_required_text "$create" "skip Steps 5 and 6"
    assert_required_text "$create" "preserve the existing local commit history"
    assert_required_text "$branch" "capture its exact full OID as \`{observed-origin-oid}\`"
    assert_required_text "$branch" "scripts/resolve-origin-push-url.sh"
    assert_required_text "$branch" "{origin-push-url-assignment}"
    assert_required_text "$branch" "git ls-remote --heads -- \"\$ORIGIN_PUSH_URL\""
    assert_required_text "$branch" "git fetch --no-tags --no-write-fetch-head -- \"\$ORIGIN_PUSH_URL\""
    assert_required_text "$branch" "git merge-base --is-ancestor \"{observed-origin-oid}\" \"{entry-commit}\""
    assert_required_text "$branch" "record \`{branch-action}=fast-forward-existing-remote\`"
    assert_required_text "$branch" "report that the remote contains commits absent locally"
    assert_required_text "$branch" "report genuine divergence"
    assert_required_text "$branch" "Never merge, reset, rebase, or invoke history rewriting"
    assert_required_text "$branch" "Never adopt a remote branch selected from a different entry checkout"
    assert_required_text "$state" "continue only when it returns no matching ref"
    assert_required_text "$state" "stop before branch creation or \`trackbed:git:recreate-commits\`"
    assert_required_text "$state" "cannot atomically prevent another actor from opening a Pull Request"
    assert_required_text "$confirmation" "REMOTE_RECOVERY_MODE=true"
    assert_required_text "$confirmation" "REMOTE_FAST_FORWARD_MODE=true"
    assert_required_text "$confirmation" "REMOTE_APPEND_MODE=true"
    assert_required_text "$confirmation" "Do not run \`git push\` in this mode"
    assert_required_text "$confirmation" "Require the authoritative remote OID to remain exactly \`{observed-origin-oid}\`"
    assert_required_text "$confirmation" "Require \`HEAD\` to remain exactly \`{entry-commit}\`"
    assert_required_text "$confirmation" "require its OID to remain exactly \`{observed-origin-oid}\`"
    assert_required_text "$confirmation" "The exact lease rejects every remote change after classification"
    assert_required_text "$confirmation" "execute Step 10 before stopping"
    assert_required_text "$confirmation" "--head \"{feature-branch}\""
    assert_required_text "$confirmation" "prevents \`gh pr create\` from offering to push or fork"
    assert_absent_text "$state" "git fetch --no-tags origin \"{rollback-origin-ref}\""

	assert_required_contracts_registered \
		pr-create-existing-remote-orchestration \
		pr-create-clean-worktree-helper \
		pr-create-existing-remote-classification \
		pr-create-existing-remote-publication

}

@test "pr-create auto mode appends dirty work to a safely reusable existing remote" {
    cd "$BATS_TEST_DIRNAME/.."
    create="skills/pr:create/SKILL.md"
    state="skills/pr:create/references/state-and-rollback.md"
    abort="skills/pr:create/references/abort-and-rollback.md"
    confirmation="skills/pr:create/references/confirmation-and-creation.md"

    assert_required_text "$create" "REMOTE_APPEND_MODE=true"
    assert_required_text "$create" "require \`AUTO_MODE=true\`"
    assert_required_text "$create" "execute Step 5"

    assert_required_text "$state" "When \`REMOTE_APPEND_MODE=true\`"
    assert_required_text "$state" "set \`{rollback-origin-oid}\` to \`{observed-origin-oid}\`"
    assert_required_text "$state" "Commit and include"
    assert_required_text "$state" "verify-clean-worktree.sh\" --allow-visible"
    assert_required_text "$state" "origin-push-url-assignment"

    assert_required_text "$confirmation" "--force-with-lease=\"refs/heads/{feature-branch}:{observed-origin-oid}\""
    assert_required_text "$abort" "### 10.0 Refuse Rollback After Local Drift"
    assert_required_text "$abort" "derive \`{rollback-expected-tip}\`"
    assert_required_text "$abort" "Otherwise require \`{recreate-input-tip}\`"
    assert_required_text "$abort" "final guard and reset in one bounded shell invocation"
    assert_required_text "$abort" "git reset --keep \"{original-commit}\""
    assert_required_text "$abort" "Never substitute \`git reset --hard\` in remote-append mode"
    assert_required_text "$abort" "shell tool's bounded timeout"
    assert_required_text "$abort" "git ls-remote --heads -- \"\$ORIGIN_PUSH_URL\""
    assert_required_text "$confirmation" "Remote append is auto-only and cannot reach this confirmation"
    assert_required_text "$create" "reject inline credentials, other credential-bearing URL syntax, executable remote-helper forms, and unsupported transports"

	assert_required_contracts_registered \
		pr-create-existing-remote-append-orchestration \
		pr-create-existing-remote-append-state \
		pr-create-existing-remote-append-publication \
		pr-create-abort-and-rollback

}

@test "pr-create clean-worktree verifier overrides hidden-untracked configuration" {
	verifier="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	repo="$BATS_TEST_TMPDIR/repo"

	git init "$repo"
	git -C "$repo" config user.name "Test User"
	git -C "$repo" config user.email "test@example.com"
	printf 'tracked\n' > "$repo/tracked.txt"
	git -C "$repo" add tracked.txt
	git -C "$repo" commit -m "initial"
	git -C "$repo" config status.showUntrackedFiles no
	printf 'hidden\n' > "$repo/untracked.txt"

	run bash -c 'cd "$1" && "$2"' _ "$repo" "$verifier"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Working tree has uncommitted or untracked changes"* ]] || false
}

@test "pr-create clean-worktree verifier rejects modified assume-unchanged content" {
	verifier="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	repo="$BATS_TEST_TMPDIR/repo"

	git init "$repo"
	git -C "$repo" config user.name "Test User"
	git -C "$repo" config user.email "test@example.com"
	printf 'tracked\n' > "$repo/tracked.txt"
	git -C "$repo" add tracked.txt
	git -C "$repo" commit -m "initial"
	git -C "$repo" update-index --assume-unchanged tracked.txt
	printf 'modified\n' > "$repo/tracked.txt"

	run bash -c 'cd "$1" && "$2"' _ "$repo" "$verifier"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Hidden tracked content differs from the index"* ]] || false
}

@test "pr-create verifier detects skip-worktree edits while allowing visible work" {
	verifier="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	repo="$BATS_TEST_TMPDIR/repo"

	git init "$repo"
	git -C "$repo" config user.name "Test User"
	git -C "$repo" config user.email "test@example.com"
	printf 'hidden\n' >"$repo/hidden.txt"
	printf 'visible\n' >"$repo/visible.txt"
	git -C "$repo" add hidden.txt visible.txt
	git -C "$repo" commit -m "initial"

	printf 'visible change\n' >"$repo/visible.txt"
	run bash -c 'cd "$1" && "$2" --allow-visible' _ "$repo" "$verifier"
	[ "$status" -eq 0 ]

	git -C "$repo" checkout -- visible.txt
	git -C "$repo" update-index --skip-worktree hidden.txt
	printf 'hidden change\n' >"$repo/hidden.txt"
	run bash -c 'cd "$1" && "$2"' _ "$repo" "$verifier"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Hidden tracked content differs from the index"* ]] || false

	printf 'visible change\n' >"$repo/visible.txt"
	run bash -c 'cd "$1" && "$2" --allow-visible' _ "$repo" "$verifier"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Hidden tracked content differs from the index"* ]] || false
}

@test "pr-create verifier accepts clean sparse-checkout omissions" {
	verifier="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	repo="$BATS_TEST_TMPDIR/sparse-repo"

	git init "$repo"
	git -C "$repo" config user.name "Test User"
	git -C "$repo" config user.email "test@example.com"
	mkdir -p "$repo/kept" "$repo/omitted"
	printf 'kept\n' >"$repo/kept/file.txt"
	printf 'omitted\n' >"$repo/omitted/file.txt"
	git -C "$repo" add .
	git -C "$repo" commit -m "initial"
	git -C "$repo" sparse-checkout init --cone
	git -C "$repo" sparse-checkout set kept
	[ ! -e "$repo/omitted/file.txt" ]

	cd "$repo"
	run "$verifier"
	[ "$status" -eq 0 ]

	printf 'visible change\n' >kept/file.txt
	run "$verifier" --allow-visible
	[ "$status" -eq 0 ]
}

@test "pr-create clean-worktree verifier fails closed when status inspection fails" {
	verifier="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/verify-clean-worktree.sh"
	repo="$BATS_TEST_TMPDIR/repo"
	fake_bin="$BATS_TEST_TMPDIR/fake-bin"
	real_git=$(command -v git)

	git init "$repo"
	mkdir -p "$fake_bin"
	printf '#!/bin/sh\nif [ "${1:-}" = status ]; then exit 73; fi\nexec "%s" "$@"\n' "$real_git" > "$fake_bin/git"
	chmod +x "$fake_bin/git"

	run bash -c 'cd "$1" && PATH="$2:$PATH" "$3"' _ "$repo" "$fake_bin" "$verifier"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Could not inspect the working tree"* ]] || false
}

@test "pr-create guidance contracts are registered and files are wired" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    create="skills/pr:create/SKILL.md"
    preflight="skills/pr:create/references/pre-validation-checks.md"
    branch="skills/pr:create/references/branch-and-platform-handling.md"
    confirmation="skills/pr:create/references/confirmation-and-creation.md"

    test -f "$create"
    test -f "$preflight"
    test -f "$branch"
    test -f "$confirmation"
    test -x "skills/pr:create/scripts/validate-branch-name.sh"
    test -x "skills/pr:create/scripts/verify-clean-worktree.sh"

    grep -qF "references/pre-validation-checks.md" "$create"
    grep -qF "references/branch-and-platform-handling.md" "$create"
    grep -qF "references/state-and-rollback.md" "$create"
    grep -qF "references/abort-and-rollback.md" "$create"
    grep -qF "references/confirmation-and-creation.md" "$create"
    grep -qF "## Step 3.5: Reject an Existing Pull Request" "$create"
    grep -qF "Inspect the agent-tracked value directly" "$create"
    grep -qF "Require the whole string to match \`[A-Za-z0-9][A-Za-z0-9._/-]*\`" "$create"
    grep -qF "git check-ref-format --branch \"{feature-branch}\"" "$create"
    grep -qF "env GH_PROMPT_DISABLED=1 gh pr list --head \"{feature-branch}\" --state open" "$create"
    grep -qF "errors are blockers, not evidence that no Pull Request exists" "$create"
    grep -qF "scripts/validate-branch-name.sh" "$branch"
    grep -qF "capture it as pinned \`{base-ref}\`" "$branch"
    grep -qF "pass \`{base-source-ref}\`, \`{base-ref}\`, and \`{base-branch}\` unchanged to both downstream skills" "$branch"
    grep -qF "git status --porcelain --untracked-files=all" "$create"
    grep -qF "scripts/verify-clean-worktree.sh" "$create"
    grep -qF "scripts/verify-clean-worktree.sh" "$confirmation"
    grep -qF "headRefOid" "$confirmation"
    grep -qF "equal \`{publication-head}\` exactly" "$confirmation"

    branch_validation_line=$(grep -nF "Inspect the agent-tracked value directly" "$create" | cut -d: -f1)
    git_validation_line=$(grep -nF "git check-ref-format --branch \"{feature-branch}\"" "$create" | cut -d: -f1)
    existing_pr_query_line=$(grep -nF "env GH_PROMPT_DISABLED=1 gh pr list --head \"{feature-branch}\" --state open" "$create" | cut -d: -f1)
    [ "$branch_validation_line" -lt "$git_validation_line" ]
    [ "$git_validation_line" -lt "$existing_pr_query_line" ]

    ! grep -qF "pr-title.XXXXXX.txt" "$confirmation" || false
    ! grep -qF "pr-body.XXXXXX.md" "$confirmation" || false
    ! grep -q -- "--body \"\$(cat <<" "$confirmation" || false
  '

	assert_required_contracts_registered \
		pr-create-gh-prevalidation \
		pr-create-existing-pr-preflight \
		pr-create-ref-trust-boundary \
		pr-create-branch-validator-script \
		pr-create-description-generation-contract \
		pr-create-linear-id-normalization \
		pr-create-branch-linear-state \
		pr-create-body-file-contract \
		pr-create-edit-loop-linear-normalization

	[ "$status" -eq 0 ]
}

@test "pr-create restores the original index when the include commit fails" {
	state="$BATS_TEST_DIRNAME/../skills/pr:create/references/state-and-rollback.md"
	block="$BATS_TEST_TMPDIR/commit-and-include.sh"
	repo="$BATS_TEST_TMPDIR/repo"
	extract_commit_and_include_block "$state" "$block"

	git init --shared=group "$repo"
	cd "$repo"
	git config user.name "Test User"
	git config user.email "test@example.com"
	printf 'initial\n' > tracked.txt
	git add tracked.txt
	git commit -m "Initial commit"
	printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

	printf 'staged\n' > staged.txt
	git add staged.txt
	printf 'unstaged\n' >> tracked.txt
	printf 'untracked\n' > untracked.txt
	index_path=$(git rev-parse --git-path index)
	chmod 0664 "$index_path"

	before_head=$(git rev-parse HEAD)
	before_index=$(git hash-object "$index_path")
	before_mode=$(file_mode "$index_path")
	before_cached=$(git diff --cached --binary)
	before_unstaged=$(git diff --binary)
	before_status=$(git status --porcelain)

	run bash "$block"
	[ "$status" -ne 0 ]
	[[ "$output" == *"restored the original Git index"* ]] || false
	[ "$(git rev-parse HEAD)" = "$before_head" ]
	[ "$(git hash-object "$index_path")" = "$before_index" ]
	[ "$(file_mode "$index_path")" = "$before_mode" ]
	[ "$(git diff --cached --binary)" = "$before_cached" ]
	[ "$(git diff --binary)" = "$before_unstaged" ]
	[ "$(git status --porcelain)" = "$before_status" ]
}

@test "pr-create preserves the index backup when restoration fails" {
	state="$BATS_TEST_DIRNAME/../skills/pr:create/references/state-and-rollback.md"
	block="$BATS_TEST_TMPDIR/commit-and-include.sh"
	repo="$BATS_TEST_TMPDIR/repo"
	fake_bin="$BATS_TEST_TMPDIR/fake-bin"
	extract_commit_and_include_block "$state" "$block"

	git init "$repo"
	cd "$repo"
	git config user.name "Test User"
	git config user.email "test@example.com"
	printf 'initial\n' > tracked.txt
	git add tracked.txt
	git commit -m "Initial commit"
	printf '#!/bin/sh\nexit 1\n' > .git/hooks/pre-commit
	chmod +x .git/hooks/pre-commit

	printf 'staged\n' > staged.txt
	git add staged.txt
	printf 'unstaged\n' >> tracked.txt
	index_path=$(git rev-parse --git-path index)
	before_head=$(git rev-parse HEAD)
	before_index=$(git hash-object "$index_path")

	mkdir -p "$fake_bin"
	printf '#!/bin/sh\nexit 73\n' > "$fake_bin/mv"
	chmod +x "$fake_bin/mv"

	run env PATH="$fake_bin:$PATH" bash "$block"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Failed to restore the original Git index. Backup remains at "* ]] || false
	[[ "$output" != *"restored the original Git index"* ]] || false
	backup_path=${output##*Backup remains at }
	backup_path=${backup_path%.}
	[ -f "$backup_path" ]
	[ "$(git hash-object "$backup_path")" = "$before_index" ]
	[ "$(git rev-parse HEAD)" = "$before_head" ]
}

@test "pr-create state and rollback guidance keeps required sections" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    state="skills/pr:create/references/state-and-rollback.md"
    abort="skills/pr:create/references/abort-and-rollback.md"

    test -f "$state"
    test -f "$abort"
    grep -q "^## Step 5: State Preservation" "$state"
    grep -q "^## Step 9.0: Restore Excluded Uncommitted Changes" "$state"
    ! grep -q "^## Step 10" "$state" || false
    grep -qF "Step 10 (abort path) lives in \`abort-and-rollback.md\`; read it only when Step 10 runs" "$state"
    grep -q "^## Step 10: Abort and Rollback" "$abort"
    grep -qF "{rollback-origin-ref}" "$state"
    grep -qF "{rollback-origin-oid}" "$state"
    grep -qF "git ls-remote --heads origin \"{rollback-origin-ref}\"" "$state"
    grep -qF "git ls-remote --heads origin \"{rollback-origin-ref}\"" "$abort"
    grep -qF "continue only when it returns no matching ref" "$state"
    grep -qF "Neither auto mode nor \`--authorize-history-rewrite\` may bypass this fresh-mode remote-absence requirement" "$state"
    grep -qF "never force-push, delete, or recreate the remote ref during automatic rollback" "$abort"
    grep -qF "Remote state: {unchanged at captured OID/absence | diverged" "$abort"
    grep -qF "Remote restoration is claimed only when the read-only comparison reports \`unchanged\`" "$abort"
    ! grep -qF "Your work has been restored to the pre-skill branch state." "$abort" || false
  '

	assert_required_contracts_registered \
		pr-create-remote-absence-contract \
		pr-create-state-restoration-contract \
		pr-create-abort-and-rollback

	[ "$status" -eq 0 ]
}

@test "pr-create auto mode includes uncommitted work and authorizes the protected reset without prompting" {
    cd "$BATS_TEST_DIRNAME/.."
    create="skills/pr:create/SKILL.md"
    state="skills/pr:create/references/state-and-rollback.md"

    assert_required_text "$create" "include all uncommitted changes by selecting **Commit and include**"
    assert_required_text "$create" "\`--manual\` -> set \`AUTO_MODE=false\`"
    assert_required_text "$create" "Auto mode authorizes the nested unstacked rewrite but does not synthesize the separate stack-wide authorization capability"
    assert_required_text "$create" "Step 5 uncommitted-work decision when \`AUTO_MODE=false\`"
    assert_required_text "$state" "If uncommitted changes are present and \`AUTO_MODE=true\`, do not prompt."
    assert_required_text "$state" "Select **Commit and include** and execute that path below."
    assert_required_text "$state" "If uncommitted changes are present and \`AUTO_MODE=false\`"

}

@test "pr-create auto mode is fail-closed and fully non-interactive" {
    cd "$BATS_TEST_DIRNAME/.."
    create="skills/pr:create/SKILL.md"
    branch="skills/pr:create/references/branch-and-platform-handling.md"
    state="skills/pr:create/references/state-and-rollback.md"
    confirmation="skills/pr:create/references/confirmation-and-creation.md"

    assert_required_text "$create" "MISSING REQUIREMENT: generated PR title/body unavailable; placeholder publication is forbidden"
    assert_required_text "$create" "Never create a Pull Request containing placeholder fallback text."
    assert_required_text "$create" "Every other \`MISSING REQUIREMENT:\` marker is blocking"
    assert_required_text "$create" "any future requirement the generator marks as missing"
    assert_absent_text "$create" "**Fallback description**"
    assert_absent_text "$create" "**Fallback title**"

    assert_required_text "$branch" "Do not ask for initials"
    assert_required_text "$branch" "feature/{issue-id-lowercase}-{sanitized-title}"
    assert_required_text "$branch" "If \`AUTO_MODE=true\`, select the first non-empty candidate"
    assert_required_text "$branch" "report a hard blocker without prompting"
    assert_required_text "$branch" "If \`AUTO_MODE=false\`, ask the user to choose from the generated candidates or provide a branch name"
    assert_required_text "$branch" "env GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never"
    assert_required_text "$branch" "NONINTERACTIVE_GIT_SSH_COMMAND=\"\${GIT_SSH_COMMAND:-\${GIT_SSH:-ssh}} -oBatchMode=yes\""
    assert_required_text "$branch" "GIT_SSH_COMMAND=\"\$NONINTERACTIVE_GIT_SSH_COMMAND\""
    assert_required_text "$state" "env GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never"

    assert_required_text "$confirmation" "env GH_PROMPT_DISABLED=1 gh pr list"
    assert_required_text "$confirmation" "env GIT_TERMINAL_PROMPT=0 GCM_INTERACTIVE=Never"
    assert_required_text "$confirmation" "shell tool's bounded timeout"
    assert_required_text "$confirmation" "If the push command exits non-zero, its remote outcome is ambiguous"
    assert_required_text "$confirmation" "never continue to \`gh pr create\` after a non-zero push status"
    assert_absent_text "$confirmation" "The generated description is saved."

}

@test "branch validator rejects shell-active names that Git itself accepts" {
	validator="$BATS_TEST_DIRNAME/../skills/pr:create/scripts/validate-branch-name.sh"
	cd "$BATS_TEST_TMPDIR"

	for hostile in \
		'feature/x;touch-pwned' \
		'feature/x$(touch-pwned)' \
		'feature/x`touch-pwned`' \
		'feature/x&touch-pwned'; do
		git check-ref-format --branch "$hostile"
		run "$validator" "$hostile"
		[ "$status" -ne 0 ]
	done

	[ ! -e touch-pwned ]
	run "$validator" "feature/abc-123_safe"
	[ "$status" -eq 0 ]
	[ "$output" = "feature/abc-123_safe" ]
}

@test "new feature branch starts at immutable entry commit and rollback restores entry checkout" {
	branch_guidance="$BATS_TEST_DIRNAME/../skills/pr:create/references/branch-and-platform-handling.md"
	state_guidance="$BATS_TEST_DIRNAME/../skills/pr:create/references/state-and-rollback.md"
	repo="$BATS_TEST_TMPDIR/repo"
	grep -qF 'git diff --name-only "{base-ref}"...HEAD' "$branch_guidance"
	grep -qF "stop without deleting any ref" "$state_guidance"
	grep -qF "{feature-branch}-recreate-backup-{recreate-input-tip}" "$state_guidance"
	! grep -qF "If branch creation fails, inspect whether Git created the ref" "$state_guidance" || false

	git init "$repo"
	git -C "$repo" config user.name "Test User"
	git -C "$repo" config user.email "test@example.com"
	printf 'base\n' >"$repo/file.txt"
	git -C "$repo" add file.txt
	git -C "$repo" commit -m "base"
	git -C "$repo" branch -M main
	printf 'local\n' >>"$repo/file.txt"
	git -C "$repo" commit -am "local entry work"

	entry_commit=$(git -C "$repo" rev-parse HEAD)
	git -C "$repo" checkout -b feature/preserved "$entry_commit"
	original_commit=$(git -C "$repo" rev-parse HEAD)
	[ "$original_commit" = "$entry_commit" ]
	[ "$(git -C "$repo" show HEAD:file.txt)" = $'base\nlocal' ]

	printf 'rewritten\n' >"$repo/file.txt"
	git -C "$repo" commit -am "simulated rewrite"
	git -C "$repo" reset --hard "$original_commit"
	git -C "$repo" checkout main
	git -C "$repo" branch -d feature/preserved

	[ "$(git -C "$repo" branch --show-current)" = "main" ]
	[ "$(git -C "$repo" rev-parse HEAD)" = "$entry_commit" ]
	! git -C "$repo" show-ref --verify --quiet refs/heads/feature/preserved || false
}

@test "pr-create accepts --rebase and its --rebase-first alias" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    create="skills/pr:create/SKILL.md"
    branch="skills/pr:create/references/branch-and-platform-handling.md"

    grep -qE "^argument-hint: .*\[--rebase\]" "$create"
    grep -qF -- "- \`--rebase\` (alias: \`--rebase-first\`) -> set \`REBASE_FIRST=true\`" "$create"
    grep -qF "When \`REBASE_FIRST=true\`" "$create"
    grep -qF "apply the protected/workbench/production branch guard" "$create"
    grep -qF "Before classifying \`{entry-branch}\` as a feature" "$branch"
    grep -qF "Do not publish a Pull Request from a production branch" "$branch"
  '
	[ "$status" -eq 0 ]
}

@test "pr-create runs Steps 1-4.5 through the read-only preflight helper" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    create="skills/pr:create/SKILL.md"
    prevalidation="skills/pr:create/references/pre-validation-checks.md"
    branch="skills/pr:create/references/branch-and-platform-handling.md"

    test -f "skills/pr:create/scripts/pr-create-preflight.py"
    [ "$(grep -c "^## Preflight Helper$" "$create")" -eq 1 ]
    helper_line=$(grep -n "^## Preflight Helper$" "$create" | cut -d: -f1)
    step_one_line=$(grep -n "^## Step 1: Pre-Validation$" "$create" | cut -d: -f1)
    [ "$helper_line" -lt "$step_one_line" ]
    grep -qF "python3 \"\${CLAUDE_PLUGIN_ROOT}/skills/pr:create/scripts/pr-create-preflight.py\"" "$create"
    grep -qF "parse it as JSON and never \`eval\` or source it" "$create"
    grep -qF "rerun the helper with the same flags plus \`--feature-branch \"{validated-candidate}\"\`" "$create"
    grep -qF "starting at \"If they differ, freeze the one effective push endpoint\"" "$create"
    grep -qF "If they differ, freeze the one effective push endpoint" "$branch"
    grep -qF "read \`references/pre-validation-checks.md\` only to word the error" "$create"
    grep -qF "rerun the helper to capture the rebased entry state" "$create"
    grep -qF "apply any protected, workbench, or production branch named in repository instructions" "$create"
    grep -qF "scripts/pr-create-preflight.py\` performs these checks" "$prevalidation"
    grep -qF "scripts/pr-create-preflight.py\` performs entry capture" "$branch"
    grep -qF "git rev-parse --git-path rebase-merge --git-path rebase-apply --git-path MERGE_HEAD" "$prevalidation"
    ! grep -qF ".git/rebase-merge" "$prevalidation" || exit 1
    ! grep -qF ".git/MERGE_HEAD" "$prevalidation" || exit 1
  '

	assert_required_contracts_registered pr-create-preflight-helper

	[ "$status" -eq 0 ]
}

@test "the fresh path resolves stack membership at the helper, the reset, each push, and creation" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    create="skills/pr:create/SKILL.md"
    recreate="skills/git:recreate-commits/SKILL.md"
    publication="skills/pr:create/references/confirmation-and-creation.md"

    ! grep -qF "STACK_RESOLVED=\$(" "$create" || exit 1
    grep -qF "The helper resolves stack membership for the current feature branch" "$create"

    skip_line=$(grep -nF "skip this initial resolution and set \`IN_STACK=false\`" "$recreate" | cut -d: -f1)
    initial_line=$(grep -nF "STACK_RESOLVED=\$(" "$recreate" | grep -vF "LATEST_STACK_RESOLVED" | head -1 | cut -d: -f1)
    latest_line=$(grep -nF "LATEST_STACK_RESOLVED=" "$recreate" | head -1 | cut -d: -f1)
    drift_line=$(grep -nF "Under \`REQUIRE_UNSTACKED=true\`, any local or server-side membership is state drift" "$recreate" | cut -d: -f1)
    reset_line=$(grep -nF "git reset --hard \"\$RESET_POINT\"" "$recreate" | head -1 | cut -d: -f1)
    [ "$skip_line" -lt "$initial_line" ]
    [ "$latest_line" -lt "$drift_line" ]
    [ "$drift_line" -lt "$reset_line" ]
    grep -qF "stop before the reset, even in auto mode or when \`--authorize-history-rewrite\` was passed" "$recreate"

    ! grep -qF "LATEST_STACK_RESOLVED" "$publication" || exit 1
    ! grep -qF "STACK_REVALIDATION_FAILED" "$publication" || exit 1
    [ "$(grep -cF "FINAL_STACK_RESOLVED=" "$publication")" -eq 3 ]
  '

	[ "$status" -eq 0 ]
}

@test "pr-create Step 10 lives in the abort-only reference" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    skill_dir="skills/pr:create"

    ! grep -rqF "Step 10 from \`state-and-rollback.md\`" "$skill_dir" || exit 1
    ! grep -rqF "Step 10 in \`references/state-and-rollback.md\`" "$skill_dir" || exit 1
    ! grep -rqF "Step 10 from \`references/state-and-rollback.md\`" "$skill_dir" || exit 1
    [ "$(grep -cF "abort-and-rollback.md" "$skill_dir/references/confirmation-and-creation.md")" -eq 3 ]
    section=$(awk "/^## Step 10: Abort and Rollback Handling\$/{found=1; next} found && /^## /{exit} found" "$skill_dir/SKILL.md")
    grep -qF "Read \`references/abort-and-rollback.md\` and execute its Step 10" <<<"$section"
    [ "$(grep -c "^### 10\.[0-4] " "$skill_dir/references/abort-and-rollback.md")" -eq 5 ]
  '

	[ "$status" -eq 0 ]
}

@test "pr-create keeps well-formed commits only on direct fresh runs without an include commit" {
	run bash -c '
    set -e
    cd "'"$BATS_TEST_DIRNAME"'/.."
    create="skills/pr:create/SKILL.md"

    keep_line=$(grep -n "^### 6.0 Keep Well-Formed Commits$" "$create" | cut -d: -f1)
    confirm_line=$(grep -n "^### 6.1 Confirm Commit Restructuring Approach$" "$create" | cut -d: -f1)
    [ "$keep_line" -lt "$confirm_line" ]
    section=$(awk "/^### 6.0 Keep Well-Formed Commits\$/{found=1; next} found && /^### /{exit} found" "$create")
    grep -qF -- "- \`FRESH_REMOTE_MODE=true\`." <<<"$section"
    grep -qF "\`{uncommitted-disposition}\` is \`none\` or \`excluded-and-stashed\`" <<<"$section"
    grep -qF "did not include the literal \`--require-generated-description\` flag" <<<"$section"
    grep -qF "none carries a flag (\`merge\`, \`autosquash\`, \`placeholder\`, or \`ai-attribution\`)" <<<"$section"
    grep -qF "\${CLAUDE_PLUGIN_ROOT}/shared/git/references/commit-conventions.md" <<<"$section"
    grep -qF "\"Fix lint\", \"Address review feedback\", or \"Fix typo\"" <<<"$section"
    grep -qF "History: kept {N} existing commits; no rewrite" <<<"$section"
    grep -qF "**Keep existing commits (recommended)**" "$create"
    grep -qF "When Step 6.0 qualified:" "$create"
    grep -qF "label: \"Keep existing commits (recommended)\"" "$create"
    grep -qF "label: \"Narrative\"" "$create"
    grep -qF "Otherwise:" "$create"
    grep -qF "keep unpublished fresh-branch commits that pass Step 6.0" "$create"
    grep -qF "trackbed:pr:create --base {base-branch} --require-generated-description" \
      "skills/code:plan-to-pr/references/shipping-contract.md"
    grep -qF "trackbed:pr:create --linear-issue {issue-id} --require-generated-description" \
      "skills/linear:issue-to-pr/references/shipping-contract.md"
    grep -qF "keeps unpublished commits that already follow the repository'\''s commit conventions" docs/shipping.md
  '

	[ "$status" -eq 0 ]
}

@test "generate-description skips its resolver for a caller-pinned base" {
	guidance="$BATS_TEST_DIRNAME/../skills/pr:generate-description/references/base-branch-resolution.md"
	block="$BATS_TEST_TMPDIR/pinned-base.sh"
	repo="$BATS_TEST_TMPDIR/repo"
	python3 - "$guidance" "$block" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text()
section = source.split("When both `BASE_BRANCH_OVERRIDE` and `BASE_COMMIT_OVERRIDE` are set", 1)[1]
block = section.split("```bash", 1)[1].split("```", 1)[0]
pathlib.Path(sys.argv[2]).write_text(block)
PY
	! grep -qF "resolve-base.sh" "$block" || false
	grep -qF "Otherwise, resolve the base/target branch with the shared plugin script." "$guidance"
	init_test_git_repo "$repo"
	cd "$repo"
	pinned=$(git rev-parse HEAD)
	git remote add origin https://github.com/acme/repo.git

	for base in refs/remotes/origin/main refs/heads/main origin/main; do
		BASE_BRANCH_OVERRIDE="$base" BASE_COMMIT_OVERRIDE="$pinned" run bash "$block"
		[ "$status" -eq 0 ]
		[ "$output" = "Base branch: main" ]
	done

	BASE_BRANCH_OVERRIDE=main BASE_COMMIT_OVERRIDE="$(printf 'a%.0s' $(seq 40))" run bash "$block"
	[ "$status" -ne 0 ]
	[[ "$output" == *"Pinned base commit does not resolve locally"* ]] || false
}

@test "PR creation carries bounded independent review evidence through description and publication" {
    run python3 - "$BATS_TEST_DIRNAME/.." <<'PYTEST'
import pathlib
import sys
root = pathlib.Path(sys.argv[1])
create = (root / "skills/pr:create/SKILL.md").read_text()
generate = (root / "skills/pr:generate-description/SKILL.md").read_text()
publish = (root / "skills/pr:create/references/confirmation-and-creation.md").read_text()
hooks = (root / "skills/linear:issue-to-pr/references/shipping-contract.md").read_text()
record = (root / "shared/implementation/references/independent-review.md").read_text()
for skill in (create, generate):
    assert "${CLAUDE_PLUGIN_ROOT}/shared/implementation/references/independent-review.md" in skill
    assert "--independent-review-line <line>" in skill
    assert "Reject duplicate, missing, or malformed values" in skill
    assert "byte-for-byte" in skill
assert "When `ADVERSARIAL_REVIEW=true`, append `--independent-review-line <line>`" in hooks
assert "also pass `--independent-review-line <line>` as one inert quoted argument, unchanged" in create
assert "use only with `--no-update`, and reject it with `--check`" in generate
assert "MISSING REQUIREMENT: independent review record missing or changed" in generate
assert "immediately before any push or `gh pr create`" in publish
assert "missing, changed, duplicate, or stale record blocks publication" in publish
assert "at most 1024 ASCII characters" in record
assert "patch ID against the full committed change" in record and "reviewed tree" in record
PYTEST
    [ "$status" -eq 0 ] || { echo "$output"; false; }
}
