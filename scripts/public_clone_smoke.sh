#!/usr/bin/env bash

set -euo pipefail

usage() {
  cat <<'EOF'
Usage: scripts/public_clone_smoke.sh [--source PATH] [--ref GIT_REF] [--worktree] [--keep-temp]

Clone the committed FinMAS repo state into a temporary directory, create a fresh
virtual environment, install dependencies, and run a small public-facing smoke suite.

Options:
  --source PATH   Source git repository to clone. Defaults to this repo root.
  --ref GIT_REF   Optional git ref to checkout after cloning.
  --worktree      Copy the current working tree, including uncommitted changes and
                  untracked non-ignored files, instead of cloning committed state.
  --keep-temp     Keep the temporary clone directory after the run.
  -h, --help      Show this help text.

Environment:
  PYTHON_BIN      Python executable to use for the fresh virtualenv.
  FINMAS_SMOKE_TESTS
                  Space-separated pytest paths to run instead of the default suite.
EOF
}

SOURCE_REPO=""
GIT_REF=""
WORKTREE_MODE=0
KEEP_TEMP=0
PYTHON_BIN="${PYTHON_BIN:-python3}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source)
      SOURCE_REPO="${2:-}"
      shift 2
      ;;
    --ref)
      GIT_REF="${2:-}"
      shift 2
      ;;
    --worktree)
      WORKTREE_MODE=1
      shift
      ;;
    --keep-temp)
      KEEP_TEMP=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      usage >&2
      exit 1
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEFAULT_SOURCE="$(cd "${SCRIPT_DIR}/.." && pwd)"
SOURCE_REPO="${SOURCE_REPO:-$DEFAULT_SOURCE}"
SOURCE_REPO="$(cd "${SOURCE_REPO}" && pwd)"

if ! git -C "${SOURCE_REPO}" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  echo "Source path is not a git repository: ${SOURCE_REPO}" >&2
  exit 1
fi

if [[ "${WORKTREE_MODE}" -eq 1 && -n "${GIT_REF}" ]]; then
  echo "--worktree and --ref cannot be used together." >&2
  exit 1
fi

if [[ -n "$(git -C "${SOURCE_REPO}" status --porcelain)" ]]; then
  if [[ "${WORKTREE_MODE}" -eq 1 ]]; then
    echo "Warning: ${SOURCE_REPO} has uncommitted changes." >&2
    echo "Testing current working tree state, which may differ from what GitHub users pull." >&2
  else
    echo "Warning: ${SOURCE_REPO} has uncommitted changes." >&2
    echo "This smoke test clones committed state only, which is what GitHub users will pull." >&2
  fi
fi

WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/finmas-public-smoke.XXXXXX")"
CLONE_DIR="${WORK_DIR}/repo"
VENV_DIR="${CLONE_DIR}/.venv-smoke"
WORKTREE_FILELIST="${WORK_DIR}/worktree-files.txt"

cleanup() {
  if [[ "${KEEP_TEMP}" -eq 1 ]]; then
    echo "Kept smoke workspace at: ${WORK_DIR}"
    return
  fi
  rm -rf "${WORK_DIR}"
}
trap cleanup EXIT

if [[ "${WORKTREE_MODE}" -eq 1 ]]; then
  if ! command -v rsync >/dev/null 2>&1; then
    echo "rsync is required for --worktree mode." >&2
    exit 1
  fi

  mkdir -p "${CLONE_DIR}"
  while IFS= read -r -d '' relpath; do
    [[ -e "${SOURCE_REPO}/${relpath}" ]] || continue
    printf '%s\0' "${relpath}" >> "${WORKTREE_FILELIST}"
  done < <(
    git -C "${SOURCE_REPO}" ls-files --cached --modified --others --exclude-standard -z
  )

  echo "Copying current working tree from ${SOURCE_REPO} into ${CLONE_DIR}"
  rsync -a --from0 --files-from="${WORKTREE_FILELIST}" "${SOURCE_REPO}/" "${CLONE_DIR}/"

  CLONED_REF="$(git -C "${SOURCE_REPO}" rev-parse --short HEAD)"
  echo "Testing working tree based on ref: ${CLONED_REF}"
else
  echo "Cloning ${SOURCE_REPO} into ${CLONE_DIR}"
  git clone --no-local "${SOURCE_REPO}" "${CLONE_DIR}" >/dev/null

  if [[ -n "${GIT_REF}" ]]; then
    git -C "${CLONE_DIR}" checkout "${GIT_REF}" >/dev/null
  fi

  CLONED_REF="$(git -C "${CLONE_DIR}" rev-parse --short HEAD)"
  echo "Testing cloned ref: ${CLONED_REF}"
fi

"${PYTHON_BIN}" -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

python -m pip install --upgrade pip
python -m pip install -r "${CLONE_DIR}/requirements.txt" pytest

DEFAULT_TESTS=(
  "tests/test_postgresql_mcp_server.py"
  "tests/test_public_repo_support.py"
  "attas/tests/test_public_clone_configs.py"
  "attas/tests/test_pulser_config_samples.py"
  "prompits/tests/test_user_agent_config.py"
  "prompits/tests/test_user_agent_routes.py"
)

if [[ -n "${FINMAS_SMOKE_TESTS:-}" ]]; then
  read -r -a TESTS_TO_RUN <<< "${FINMAS_SMOKE_TESTS}"
else
  TESTS_TO_RUN=("${DEFAULT_TESTS[@]}")
fi

SELECTED_TESTS=()
SKIPPED_TESTS=()
for test_path in "${TESTS_TO_RUN[@]}"; do
  if [[ -e "${CLONE_DIR}/${test_path}" ]]; then
    SELECTED_TESTS+=("${test_path}")
  else
    SKIPPED_TESTS+=("${test_path}")
  fi
done

if [[ "${#SKIPPED_TESTS[@]}" -gt 0 ]]; then
  echo "Skipping missing smoke tests in this snapshot:"
  printf '  %s\n' "${SKIPPED_TESTS[@]}"
fi

if [[ "${#SELECTED_TESTS[@]}" -eq 0 ]]; then
  echo "No requested smoke tests were found in the temporary snapshot." >&2
  if [[ "${WORKTREE_MODE}" -eq 0 ]]; then
    echo "If you want to test latest local changes, rerun with --worktree." >&2
  fi
  exit 1
fi

echo "Running smoke suite:"
printf '  %s\n' "${SELECTED_TESTS[@]}"

cd "${CLONE_DIR}"
python -m pytest -q "${SELECTED_TESTS[@]}"

echo "Public clone smoke test passed for ${CLONED_REF}."
