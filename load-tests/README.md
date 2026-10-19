# Load Tests

These k6 scripts exercise the liveness endpoint. Install k6, start the API, then run `k6 run load-tests/smoke-test.js`. Load and stress scripts use the same `BASE_URL` environment variable; only run them against an environment intended for testing.