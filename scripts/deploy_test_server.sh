#!/usr/bin/env bash
set -Eeuo pipefail

readonly REPOSITORY_DIR="/home/ubuntu/backend"
readonly SERVICE_NAME="gdam-backend"
readonly LOCAL_HEALTH_URL="http://127.0.0.1:8000/"
readonly EXPECTED_SHA="${1:?Expected Git commit SHA is required}"

previous_sha=""
deployment_started="false"
requirements_changed="false"

wait_for_health() {
    local attempt
    for attempt in {1..12}; do
        if curl --fail --silent --show-error --max-time 5 "${LOCAL_HEALTH_URL}" >/dev/null; then
            return 0
        fi
        sleep 5
    done
    return 1
}

fail() {
    echo "$1" >&2
    return 1
}

rollback() {
    local exit_code=$?
    trap - ERR HUP INT TERM

    if [[ "${deployment_started}" == "true" && -n "${previous_sha}" ]]; then
        echo "Deployment failed. Rolling back to ${previous_sha}."
        cd "${REPOSITORY_DIR}"
        git reset --hard "${previous_sha}"
        if [[ "${requirements_changed}" == "true" ]]; then
            .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
        fi
        sudo -n systemctl restart "${SERVICE_NAME}"
        wait_for_health || true
    fi

    exit "${exit_code}"
}

trap rollback ERR HUP INT TERM

cd "${REPOSITORY_DIR}"

if [[ -n "$(git status --porcelain)" ]]; then
    fail "Refusing to deploy because ${REPOSITORY_DIR} has uncommitted changes."
fi

if [[ "$(git branch --show-current)" != "main" ]]; then
    fail "Refusing to deploy because the server checkout is not on main."
fi

previous_sha="$(git rev-parse HEAD)"
git fetch origin main
git merge-base --is-ancestor "${previous_sha}" "${EXPECTED_SHA}"

if ! git diff --quiet "${previous_sha}" "${EXPECTED_SHA}" -- requirements.txt; then
    requirements_changed="true"
fi

deployment_started="true"
git merge --ff-only "${EXPECTED_SHA}"

if [[ "$(git rev-parse HEAD)" != "${EXPECTED_SHA}" ]]; then
    fail "Checked-out commit does not match the commit validated by GitHub Actions."
fi

if [[ "${requirements_changed}" == "true" ]]; then
    .venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
fi

.venv/bin/python -m compileall -q app scripts tests
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/create_tables.py

sudo -n systemctl restart "${SERVICE_NAME}"
sudo -n systemctl is-active --quiet "${SERVICE_NAME}"
wait_for_health

deployment_started="false"
trap - ERR HUP INT TERM
echo "Successfully deployed ${EXPECTED_SHA}."
