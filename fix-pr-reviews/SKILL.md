---
name: fix-pr-reviews
description: Assess, address, and resolve all review comments on a GitHub PR. Fix issues, push, verify tests pass, update PR description, resolve merge conflicts, and confirm CI is green. Use when a PR has review comments that need fixing.
allowed-tools:
  - Read
  - Write
  - Edit
  - Grep
  - Glob
  - Bash
  - Agent
  - WebFetch
---

# Fix PR Reviews

Systematically resolve every review comment on a GitHub PR, push fixes, verify tests and CI, and update the PR description to reflect the current state.

## Inputs

The user provides one of:
- A PR number (e.g., `#42`, `42`)
- A PR URL (e.g., `https://github.com/owner/repo/pulls/42`)
- Nothing — auto-detect the current branch's open PR

If no input is provided, detect via:
```bash
gh pr view --json number,url --jq '.number' 2>/dev/null
```

## Process

### Phase 1: Gather Context

1. **Fetch PR metadata:**
   ```bash
   gh pr view <number> --json title,body,state,mergeable,mergeStateStatus,baseRefName,headRefName,statusCheckRollup,reviewDecision
   ```

2. **Fetch all review comments** (Copilot, human reviewers, bots):
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number}/comments --jq '.[] | {id: .id, path: .path, line: .line, body: .body, user: .user.login, in_reply_to_id: .in_reply_to_id}'
   ```

3. **Fetch PR reviews** (overall review status):
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number}/reviews --jq '.[] | {user: .user.login, state: .state, body: .body}'
   ```

4. **Check CI status:**
   ```bash
   gh pr checks <number> --json name,state,conclusion
   ```

5. **Ensure working on the correct branch:**
   ```bash
   gh pr view <number> --json headRefName --jq '.headRefName'
   git checkout <branch>
   git pull origin <branch>
   ```

### Phase 2: Categorize Comments

Group all comments by priority:

| Priority | Description | Action |
|----------|-------------|--------|
| **Critical** | Security issues, logic bugs, broken behavior, type errors | Fix immediately |
| **Important** | Score inflation, missing dedup, unimplemented features promised in PR description | Fix before merge |
| **Style** | Tab vs spaces, unused imports, naming conventions | Fix in batch |
| **Informational** | Suggestions, future improvements, questions | Respond only if clarification needed |

For each comment, read the actual source file at the referenced path and line to understand the full context before deciding how to fix it.

### Phase 3: Fix Issues

For each comment, in priority order:

1. **Read the source file** at the referenced path/line
2. **Understand the actual issue** — don't just apply the suggestion blindly; verify it makes sense in context
3. **Fix the code** — make the minimal change that addresses the concern
4. **Verify the fix doesn't break anything** — run the relevant test file:
   ```bash
   python -m pytest tests/test_<module>.py -v --tb=short
   ```
5. **Track progress** — mentally check off each comment as resolved

When fixing, follow these rules:
- **Don't over-fix.** Address exactly what the reviewer said. Don't refactor surrounding code.
- **Don't introduce new issues.** Run tests after each file change.
- **Preserve behavior.** If a reviewer says "consider X," verify X doesn't break existing tests before applying.
- **If a comment is wrong or inapplicable,** note it but don't blindly apply it. Explain in the PR reply why it was skipped.

### Phase 4: Verify

After all fixes:

1. **Run full test suite:**
   ```bash
   python -m pytest tests/ -q --tb=line
   ```
   (Adapt command to the project's test runner — npm test, cargo test, etc.)

2. **Run linter:**
   ```bash
   ruff check src/ && mypy src/
   ```
   (Adapt to project's lint tooling.)

3. **Check for merge conflicts:**
   ```bash
   git fetch origin <base-branch>
   git merge-base --is-ancestor origin/<base-branch> HEAD && echo "Up to date" || echo "Needs rebase"
   ```

4. **If merge conflicts exist:** resolve them, run tests again, commit the resolution.

### Phase 5: Manual Test Plan Verification

Check the PR description for any unchecked manual test items (lines matching `- [ ]`). For each:

1. **If the test can run non-interactively** — run it and verify the output.
2. **If the test requires interactive input** — prompt the user to run it in their terminal. Provide the exact command. Wait for confirmation or output before marking it complete.
3. **Update the PR description** to check off completed items (`- [x]`).

If there are no manual test items, skip this phase.

### Phase 6: Commit and Push

1. **Stage only changed files** — never use `git add -A` or `git add .`:
   ```bash
   git add <specific-files>
   ```

2. **Write a clear commit message** summarizing all fixes:
   ```bash
   git commit -m "$(cat <<'EOF'
   Fix <reviewer> review issues: <brief summary>

   - file.py: <what was fixed>
   - other.py: <what was fixed>
   EOF
   )"
   ```

3. **Push:**
   ```bash
   git push origin <branch>
   ```

### Phase 7: Resolve Review Threads

After all fixes are pushed, resolve each review thread on GitHub via GraphQL:

1. **Fetch unresolved thread IDs:**
   ```bash
   gh api graphql -f query='
   query {
     repository(owner: "<owner>", name: "<repo>") {
       pullRequest(number: <number>) {
         reviewThreads(first: 50) {
           nodes {
             id
             isResolved
             comments(first: 1) {
               nodes { body }
             }
           }
         }
       }
     }
   }' --jq '.data.repository.pullRequest.reviewThreads.nodes[] | select(.isResolved == false) | .id'
   ```

2. **Resolve each thread** that was addressed:
   ```bash
   gh api graphql -f query='
   mutation {
     resolveReviewThread(input: {threadId: "<thread_id>"}) {
       thread { isResolved }
     }
   }'
   ```

   Only resolve threads whose underlying issue was actually fixed. If a comment was skipped (informational, inapplicable, or disagreed with), leave it unresolved and reply explaining why.

### Phase 8: Update PR

1. **Update the PR description** to reflect current state:
   - Mark resolved test plan items as checked `[x]`
   - Add a section listing all review comments addressed
   - Update test counts if they changed
   ```bash
   gh pr edit <number> --body "$(cat <<'EOF'
   <updated body>
   EOF
   )"
   ```

2. **Verify CI runs green** after push:
   ```bash
   gh pr checks <number>
   ```
   If CI fails, read the failure, fix it, push again. Repeat until green.

3. **Check merge status:**
   ```bash
   gh pr view <number> --json mergeable,mergeStateStatus
   ```

### Phase 9: Report

Display a summary:

```
PR #<number> Review Fixes
=========================
Comments addressed: <N>/<total>
  - Critical: <N> fixed
  - Important: <N> fixed
  - Style: <N> fixed
  - Skipped: <N> (with reasons)
Threads resolved: <N>/<total>

Tests: <passed> passed, <failed> failed, <skipped> skipped
Lint: clean / <N> issues
CI: green / pending / failing
Merge status: clean / conflicts / blocked

Commits pushed: <N>
```

## Edge Cases

### Multiple reviewers
Process all reviewers' comments together, sorted by file (batch fixes per file to minimize test runs).

### Threaded discussions
If a comment has replies (`in_reply_to_id`), read the full thread to understand the resolution before fixing. Don't fix something that was already discussed and resolved.

### Outdated comments
If a comment references a line that no longer exists (file was restructured), verify whether the issue still applies in the current code. If not, skip and note it.

### CI with no checks configured
If `statusCheckRollup` is empty, report "No CI checks configured" and rely on local test results.

### Reviewer requests changes but no specific comments
Read the review body for general feedback and apply it. If unclear, ask the user for guidance.

## Anti-patterns — do NOT do these

- Blindly applying every suggestion without reading the code
- Using `git add -A` or `git add .` (catches unintended files)
- Skipping tests between fixes (a fix can break other things)
- Ignoring failing tests and pushing anyway
- Marking review comments as resolved without actually fixing them
- Rewriting the PR description from scratch instead of updating it
- Force-pushing without asking (rewrites history others may depend on)
- Applying fixes to the wrong branch
- Committing unrelated changes alongside review fixes
