#!/bin/bash

uv run python -m Jobstreet.jobstreet &
uv run python -m Indeed.indeed &
uv run python -m LinkedIn.linkedin &

wait

echo "All job search tasks completed."