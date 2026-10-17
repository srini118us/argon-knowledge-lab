# run_sql safety boundary: threat model and honest limits

The `run_sql` guard is **not** a hardened SQL firewall and is **not** claimed to be universally
secure. It is a regex-and-allowlist filter in front of a trusted, synthetic, local DuckDB. This
note states what it defends, what it does not, and why the residual risk is acceptable for this
experiment — so no one mistakes "the test vectors pass" for "the boundary is airtight".

## What actually keeps the experiment safe (three layers)

1. **The data is synthetic and the DB is local.** There are no real secrets, credentials, or
   customer data to exfiltrate, and no production system to damage. This is the primary reason
   the boundary does not need to be bulletproof.
2. **Process isolation of the answer key.** The agent process is launched with `sim/` and
   `tools/` reachable but not `grade/` or `spec/` (see `tools/isolation.py`). The key is never
   on the agent's path. `run_sql` tiers map only to the simulated world tables, never to the key.
3. **The `run_sql` filter itself** (defence in depth), described below.

The filter is layer 3, not the whole defence. If it has a gap, layers 1 and 2 still hold.

## What the filter blocks (verified by `tests/test_sql_adversarial.py`)

- Writes and DDL in any case or with comments between tokens: `DELETE`, `UPDATE`, `INSERT`,
  `DROP`, `TRUNCATE`, `ALTER`, `CREATE`, `CREATE OR REPLACE VIEW`.
- Stacked/multiple statements (`SELECT 1; DROP TABLE ...`).
- Filesystem and external access: `read_csv`, `read_parquet`, `glob`, `ATTACH`, `COPY`,
  `INSTALL`, `LOAD`, `PRAGMA`.
- Cross-tier access, including these evasions that were tested and are blocked: direct table,
  **double-quoted identifier** (`"dbx_ar_mart"`), schema-qualified (`main.dbx_ar_mart`), scalar
  subquery, `IN (SELECT ... FROM other_tier)`, CTE wrapping another tier, `UNION` across tiers,
  and mixed case.
- String literals and comments are handled so a keyword inside a string is not a false positive.

The double-quoted-identifier bypass was found during adversarial probing in Phase 4 and fixed
(the FROM/JOIN matcher now strips quotes before tier matching). It is called out here because it
is exactly the kind of gap a regex parser can have.

## Known limitations (NOT claimed to be covered)

- **Denylist, not allowlist, of functions.** The guard blocks known-dangerous functions but does
  not enumerate every safe one. A harmless read-only scalar such as `setseed()` is allowed
  (asserted in `test_known_limitation_arbitrary_readonly_function_is_not_blocklisted`). If a
  future DuckDB build shipped a read-only-looking function that could reach the filesystem or
  network, the denylist would need updating. Mitigation: layers 1 and 2 above; the DB is
  synthetic and the key is off-path.
- **Regex parsing, not a real SQL parser.** The guard tokenises with regular expressions after
  stripping comments and string literals. This is adequate for the tested vectors but is not a
  full grammar. An adversary with a novel syntactic trick could, in principle, find a parse the
  regex misreads. The correct hardening, if this ever ran against real data, is to execute on a
  genuinely read-only DuckDB connection (`access_mode=READ_ONLY`) opened over a copy, and/or a
  per-tier connection that only attaches that tier's tables — so tier isolation and read-only
  are enforced by the engine, not by a filter. That is noted as future work; it is not needed
  for a synthetic benchmark.
- **Statement timeout is best-effort.** `SET statement_timeout` is applied but a pathological
  query is bounded by DuckDB, not by the filter.

## Bottom line

For this experiment — synthetic data, local DB, key off-path — the filter is a reasonable
defence-in-depth layer and the tested evasions are blocked. It should not be reused as a
general-purpose SQL firewall without replacing the regex filter with engine-enforced read-only
and per-tier isolation.
