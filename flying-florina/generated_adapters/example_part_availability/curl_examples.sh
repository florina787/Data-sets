#!/usr/bin/env sh
# See README.md; requires a demo token.
curl -s -H "Authorization: Bearer $TOKEN" http://127.0.0.1:8100/v1/parts/P-7731/availability
