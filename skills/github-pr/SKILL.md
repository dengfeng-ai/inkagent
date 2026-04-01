---
name: github-pr
description: >
  Implement code changes and create a GitHub PR, or iterate on an existing PR based on review feedback. Triggers: "create a PR", "open a pull request", "implement X and create a PR", "fix the review comments on PR #42", "update my PR", or any request involving code changes + GitHub PR.
---

# GitHub PR Skill

A skill for implementing code changes on a feature branch and creating a GitHub Pull Request, or iterating on an existing PR based on review feedback.

---

## Determine Mode

Before starting, determine which mode applies:

- **New PR** — the user wants to implement something new and open a PR. Required info: **repo URL**. Follow all steps below.
- **PR Iteration** — the user wants to update an existing PR (e.g. "fix the review comments on PR #42", "update my PR"). Required info: **repo URL** + **PR number or PR URL**. Skip Step 2 (branch creation) and Step 6 (PR creation).

If the user hasn't provided the required info, ask for it before proceeding. For PR Iteration, extract the PR number from the URL if a full URL is given (e.g. `https://github.com/owner/repo/pull/42` → PR #42).

---

## Full Workflow

### Step 0: Pre-flight Checks

Before doing anything, verify the environment is ready.

**Check `gh` CLI is installed:**
```bash
gh --version
```
If not found, stop and tell the user:
> "`gh` CLI is not installed. Please install it from https://cli.github.com/, then run `gh auth login` to authenticate."

---

### Step 1: Fresh Clone

Every run gets its own isolated working directory, enabling multiple agents to work concurrently without conflict.

**Generate a unique directory using a short UUID:**
```bash
SHORT_UUID=$(python3 -c "import uuid; print(str(uuid.uuid4())[:7])")
REPO_NAME=$(basename <repo-url> .git)   # e.g. "inkagent"
WORK_DIR=~/.inkagent/repos/${REPO_NAME}-${SHORT_UUID}  # e.g. ~/.inkagent/repos/inkagent-a3f2c1d
```

**Clone into it:**
```bash
mkdir -p ~/.inkagent/repos
git clone <repo-url> "$WORK_DIR"
cd "$WORK_DIR"
```

> The repo URL is provided by the user at the start of each session. No need to check for conflicts — every run has a unique directory.

---

### Step 2: Set Up Branch

#### New PR — create a feature branch

Based on the user's request, determine:
- **Branch type**: `feature`, `fix`, `chore`, `refactor`, `docs`, `test`
- **Branch name**: short, kebab-case description of the change

```bash
git checkout -b <type>/<short-description>
```

**Examples:**
- `feature/add-user-auth`
- `fix/correct-date-parsing`
- `chore/update-dependencies`
- `refactor/extract-payment-service`

#### PR Iteration — checkout the existing branch

Get the branch name from the PR number:
```bash
gh pr view <pr-number> --json headRefName -q .headRefName
```

Then checkout:
```bash
git checkout <branch-name>
```

---

### Step 3: Implement the Feature

Write the code to fulfill the user's request. Follow existing code style and conventions in the repository.

---

### Step 4: Commit Changes

Review changes, then stage and commit using **Conventional Commits** format:

```bash
git status
git diff
```

Review the output carefully. Only stage files relevant to the change — never blindly `git add .`. Exclude secrets (`.env`, credentials), build artifacts, and unrelated files.

```bash
git add <file1> <file2> ...
git commit -m "<type>(<scope>): <short description>"
```

**Types:** `feat`, `fix`, `chore`, `refactor`, `docs`, `test`, `style`, `perf`

**Examples:**
- `feat(auth): add JWT login endpoint`
- `fix(parser): correct off-by-one error in date parsing`
- `chore(deps): update axios to v1.6`

If the change is large, add a body:
```bash
git commit -m "feat(auth): add JWT login endpoint

Implements POST /auth/login with bcrypt password verification
and 7-day JWT token expiry."
```

---

### Step 5: Push Feature Branch

```bash
git push origin <branch-name>
```

---

### Step 6: Create Pull Request (New PR only)

> **PR Iteration**: skip this step — the PR already exists. After pushing, print the existing PR URL:
> ```bash
> gh pr view <pr-number> --json url -q .url
> ```

Use `gh` CLI to create the PR with auto-generated title and description.

**PR Title:** Derive from the commit message (Conventional Commits style), e.g.:
`feat(auth): add JWT login endpoint`

**PR Description template (in English):**

```markdown
## Summary
<1-3 sentence description of what this PR does and why>

## Changes
- <bullet point for each meaningful change>
- <keep it concise and scannable>

## How to Test
<step-by-step instructions for a reviewer to verify the change works>
```

**Command:**

Write the description to a temp file first to ensure newlines render correctly, then use `--body-file`:

```bash
PR_BODY_FILE=$(mktemp)
cat > "$PR_BODY_FILE" << 'EOF'
## Summary
<summary>

## Changes
- <change 1>
- <change 2>

## How to Test
<how to test>
EOF

DEFAULT_BRANCH=$(gh repo view --json defaultBranchRef -q .defaultBranchRef.name)

gh pr create \
  --title "<PR title>" \
  --body-file "$PR_BODY_FILE" \
  --base "$DEFAULT_BRANCH" \
  --head <branch-name>

rm -f "$PR_BODY_FILE"
```

After creation, print the PR URL for the user.

---

### Step 7: Clean Up

Delete the isolated working directory — it's no longer needed:

```bash
rm -rf "$WORK_DIR"
```

> The remote feature branch is kept alive for the open PR. It will be deleted after merge.

---

## Error Handling

| Situation | Action |
|---|---|
| `gh` not installed | Stop, provide install link: https://cli.github.com/ |
| Not authenticated with `gh` | Run `gh auth login` |
| Clone fails (auth / repo not found) | Report error and stop; check repo URL and `gh` auth |
| Push rejected (new PR, branch name conflict) | Pick a different branch name and retry |
| Push rejected (PR iteration, diverged history) | Use `git pull --rebase` to sync, then push again |
| PR already exists for branch | Notify user and skip PR creation step |