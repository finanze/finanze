#!/usr/bin/env bash

if [ "$#" -eq 0 ]; then
  echo "::error::No command provided for retry" >&2
  exit 2
fi

max_attempts="${RETRY_ATTEMPTS-3}"
if [[ ! "$max_attempts" =~ ^[1-9][0-9]?$ ]]; then
  echo "::error::RETRY_ATTEMPTS must be an integer between 1 and 99" >&2
  exit 2
fi

for ((attempt = 1; attempt <= max_attempts; attempt++)); do
  if "$@"; then
    exit 0
  else
    status=$?
  fi

  if [ "$attempt" -eq "$max_attempts" ]; then
    echo "::error::Command failed after $max_attempts attempts with exit code $status" >&2
    exit "$status"
  fi

  echo "::warning::Command failed with exit code $status on attempt $attempt/$max_attempts; retrying" >&2
  sleep "$((attempt * 10))"
done
