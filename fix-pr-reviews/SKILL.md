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
   gh api repos/{owner}/{repo}/pulls/{number}/comments --paginate --jq '.[] | {id: .id, path: .path, line: .line, body: .body, user: .user.login, in_reply_to_id: .in_reply_to_id}'
   ```

3. **Fetch PR reviews** (overall review status):
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number}/reviews --paginate --jq '.[] | {user: .user.login, state: .state, body: .body}'
   ```

4. **Check CI status:**
   ```bash
   gh pr checks <number> --json name,state,conclusion
   ```

5. **Ensure working on the correct branch:**
   ```bash
   gh pr view <number> --json headRefName,baseRefName --jq '"head: " + .headRefName + "\nbase: " + .baseRefName'
   git checkout <head-branch>
   git pull --no-rebase origin <head-branch>
   ```

6. **Ensure working tree is clean, then sync with base branch** to avoid working on stale code:
   ```bash
   # Check for uncommitted changes
   git status --porcelain
   ```
   If there are uncommitted changes, either commit them or stash them (`git stash push -m "temp: pre-base-sync"`) before continuing.

   ```bash
   git fetch origin <base-branch>
   git merge origin/<base-branch> --no-edit
   ```
   - If the merge is clean, continue to Phase 2.
   - If there are conflicts, resolve them now using the process in Phase 6 step 4, run tests, and commit the merge before proceeding.
   - If the conflict is too complex to resolve confidently, ask the user before continuing.

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

3. **Check for merge conflicts** (do not merge yet — review fixes are uncommitted):
   ```bash
   git fetch origin <base-branch>
   git merge-base --is-ancestor origin/<base-branch> HEAD && echo "Up to date" || echo "Needs merge after commit"
   ```
   Note the result. The actual base-branch merge happens in Phase 6 after review fixes are committed, so the working tree stays clean.

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

3. **Sync with base branch** (now safe — review fixes are committed):
   ```bash
   git fetch origin <base-branch>
   git merge origin/<base-branch> --no-edit
   ```
   If already up to date, skip to step 5. If conflicts arise, proceed to step 4.

4. **If merge conflicts arise,** resolve them systematically:

   a. **List conflicted files:**
      ```bash
      git diff --name-only --diff-filter=U
      ```

   b. **For each conflicted file:**
      - Read the file and understand both sides of the conflict
      - If the conflict is in a file also touched by review fixes, preserve the review fixes while incorporating base branch changes
      - Edit to resolve all conflict markers (`<<<<<<<`, `=======`, `>>>>>>>`)
      - Stage the resolved file:
        ```bash
        git add <file>
        ```

   c. **After all conflicts are resolved:**
      ```bash
      git commit --no-edit
      ```

   d. **Re-run the full test suite** to verify nothing broke in the merge resolution.

   e. **If a conflict is too complex** (e.g., large structural changes on both sides), ask the user before resolving. Show the conflicted files and both sides of the diff.

   **Strategy:** Always use `merge`, never `rebase` — rebase rewrites history that reviewers have already seen. The merge commit makes the integration point visible in history.

5. **Push:**
   ```bash
   git push origin <branch>
   ```

### Phase 7: Resolve Review Threads

After all fixes are pushed, reply to each comment and resolve threads on GitHub:

1. **Reply to each addressed comment** with what was done:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies \
     -f body="Fixed — <brief description of what was changed>"
   ```

   For skipped comments, reply explaining why:
   ```bash
   gh api repos/{owner}/{repo}/pulls/{number}/comments/{comment_id}/replies \
     -f body="Skipped — <reason: inapplicable, already resolved in discussion, or disagree with rationale>"
   ```

   Keep replies concise — one sentence per reply.

2. **Fetch unresolved thread IDs** (paginate to catch all threads):
   ```bash
   # First page
   gh api graphql -f query='
   query {
     repository(owner: "<owner>", name: "<repo>") {
       pullRequest(number: <number>) {
         reviewThreads(first: 100) {
           pageInfo { hasNextPage endCursor }
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
   }' --jq '.data.repository.pullRequest.reviewThreads'
   ```
   If `pageInfo.hasNextPage` is true, fetch additional pages using `after: "<endCursor>"`:
   ```bash
   gh api graphql -f query='
   query {
     repository(owner: "<owner>", name: "<repo>") {
       pullRequest(number: <number>) {
         reviewThreads(first: 100, after: "<endCursor>") {
           pageInfo { hasNextPage endCursor }
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
   }' --jq '.data.repository.pullRequest.reviewThreads'
   ```
   Repeat until `hasNextPage` is false. Collect all unresolved thread IDs:
   ```bash
   # From each page's output, filter unresolved threads:
   # .nodes[] | select(.isResolved == false) | .id
   ```

3. **Resolve each thread** that was addressed:
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
