#!/bin/bash

uv run python -m Jobstreet.jobstreet
uv run python -m LinkedIn.linkedin 
uv run python -m Indeed.indeed 

wait

echo "All job search tasks completed."