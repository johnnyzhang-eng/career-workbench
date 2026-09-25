# Candidate context in a first recruiting plan

Issue #66 links a selected discovery lead to a recruiting goal. The lead remains
`待核查`. This adapter reads only `agent/local` rows from the current workspace's
`discovery.sqlite3`; a missing discovery database is an empty state and is not
created by the read path. The browser sends only a candidate ID. The server
re-reads that ID immediately before building the proposal. Its URL and
observation time become source references, while every proposed recruiting
task stays `source_kind=goal` and `task_kind=custom`. The older job state
machine alone can support an actual submitted receipt.

The user can choose no lead. A selected lead adds its existing unknowns to the
proposal and changes the first three steps to locating the official page,
checking eligibility, and recording verified versus unknown fields. The
source page may itself be an aggregator; the interface labels it accordingly.
The source reference remains available in an expandable detail.

Verification used a fictional local discovery record and goal:

- Missing DB, malformed URL, removed lead, invalid ID, read-only lookup, and
  candidate plus SQL/Python/algorithm proposal are covered by unit tests.
- HTTP test checks list, server-side ID validation, and proposed goal tasks.
- In the browser, selected the fictional candidate and SQL focus, generated a
  ten-item pending proposal, and reloaded to see the source/unknowns persist.
  It was inactive until explicit acceptance. After acceptance, daily sync and
  reload showed ten future tasks still marked as not started.
- Full local suite: 103 tests. Inline JavaScript passed `node --check`.
  Privacy scanner: 89 share-candidate files, 0 flags. The browser data stayed
  under ignored `private/` and contains only fictional records.

Real job availability, eligibility, submitted state, and a person's learning
ability are outside these checks. Review the exact job source before any real
plan or application.
