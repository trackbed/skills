# Verify a Showtime Handoff

`trackbed:conductor:showtime` can ask an idle workspace's chat to create a Pull Request for committed work. Read the shared Showtime handoff reference named in Step 0. Require the exact current command, `/trackbed:pr-create --showtime` in Claude Code or `$trackbed:pr:create --showtime` in Codex, and a `senderSessionId` from Conductor.

After verification succeeds, run normal auto mode on the clean checkout using the existing preflight, description, branch, and publication gates. Stop before any write if `git status --porcelain --untracked-files=normal` reports an uncommitted change. The handoff supplies no additional rewrite, stacking, or scope flags.
