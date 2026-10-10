set lazy
set positional-arguments
set quiet
set script-interpreter := ['bash', '-euo', 'pipefail']
set shell := ['bash', '-euo', 'pipefail', '-c']

FORGEJO_URL := env_var_or_default('FORGEJO_URL', 'http://nas.homelab.internal:9003')
TICKETS_REPO := 'soulwhisper/homelab-tickets'
# justfile_directory() in a module is the root justfile's dir (repo root).
FORGEJO_DIR := justfile_directory() / "infrastructure/forgejo"

[private]
default:
  @just --list forgejo

# Token: $FORGEJO_TOKEN_FILE (default ~/forgejo_tickets.key), else 1Password
# forgejo.pat_tickets. Printed only to the caller's pipe, never logged.
[private]
[script]
_token:
  file="${FORGEJO_TOKEN_FILE:-$HOME/forgejo_tickets.key}"
  if [[ -r "$file" ]]; then
    tr -d '[:space:]' < "$file"
  else
    just infra _op_get_secret forgejo pat_tickets
  fi

[doc('Sync skills/ and workflows/ into the homelab-tickets repo (learnings/ untouched)')]
[script]
sync:
  token="$(just forgejo _token)"
  : "${token:?empty Forgejo token}"
  work="$(mktemp -d)"
  trap 'rm -rf "$work"' EXIT
  # Token via an ephemeral credential header, not the clone URL, so it never
  # lands in .git/config, process args of git children, or error output.
  export GIT_CONFIG_COUNT=1 GIT_CONFIG_KEY_0=http.extraHeader \
    GIT_CONFIG_VALUE_0="Authorization: token ${token}"
  remote="{{FORGEJO_URL}}/{{TICKETS_REPO}}.git"
  if git ls-remote --exit-code --heads "$remote" main >/dev/null 2>&1; then
    git clone --quiet --depth 1 --branch main "$remote" "$work/repo"
  else
    # Empty repo: start main from scratch.
    git init --quiet --initial-branch main "$work/repo"
    git -C "$work/repo" remote add origin "$remote"
  fi
  cd "$work/repo"
  # Mirror only the two tracked dirs. No --delete outside them: learnings/
  # is written by the lessons workflow and must never be touched by sync.
  mkdir -p skills .forgejo/workflows
  rsync -a --delete --exclude '__pycache__' "{{FORGEJO_DIR}}/skills/" skills/
  rsync -a --delete --exclude '__pycache__' "{{FORGEJO_DIR}}/workflows/" .forgejo/workflows/
  git add skills .forgejo/workflows
  if git diff --cached --quiet; then
    echo "✅ homelab-tickets already in sync"
    exit 0
  fi
  git -c user.name="home-ops sync" -c user.email="ai-ops@noirprime.com" \
    commit --quiet -m "sync: skills + workflows from home-ops@$(git -C "{{FORGEJO_DIR}}" rev-parse --short HEAD)"
  git push --quiet origin HEAD:main
  echo "✅ synced homelab-tickets: $(git log --oneline -1)"
