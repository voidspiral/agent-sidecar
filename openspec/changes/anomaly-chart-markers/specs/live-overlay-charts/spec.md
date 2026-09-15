## ADDED Requirements

### Requirement: Overlay snapshot includes elapsed-time markers
The submit-host live plot consumer SHALL read `events/*_markers.jsonl` and
include a `markers` array in the snapshot. Each marker MUST expose
`reason_code`, `host`, and `x` as seconds relative to snapshot `t0` (first
series sample when present). Missing marker files MUST yield `markers: []`
and MUST NOT fail the snapshot. Growing marker files MUST appear in a later
poll. Markers outside the four point codes (`mpi_abort`, `mpi_segfault`,
`slurm_oom`, `node_local`) MUST be ignored.

#### Scenario: Abort marker is relative to series t0
- **WHEN** series samples start at ts 10.0 and a `mpi_abort` marker has ts 12.5
- **THEN** the snapshot contains a marker with `reason_code=mpi_abort` and
  `x=2.5`

#### Scenario: No marker files means empty markers
- **WHEN** `series/` has JSONL and `events/` has no `*_markers.jsonl`
- **THEN** `markers` is an empty list and metric series are unchanged

#### Scenario: Marker append appears in a later snapshot
- **WHEN** a new marker JSONL line is appended after a snapshot
- **THEN** a subsequent snapshot includes the additional marker

#### Scenario: Snapshot without series still succeeds
- **WHEN** `series/` is empty and a marker file exists
- **THEN** the snapshot MUST NOT fail and MUST include `markers`

### Requirement: Browser overlays marker lines on every metric chart
The live plot page SHALL draw a vertical line and a label box
(`host` plus `reason_code`) for each snapshot marker on all six metric
charts. The page MUST NOT load an annotation plugin from a CDN. Healthy
series jitter without markers MUST leave charts without those overlays.

#### Scenario: HTML includes marker drawing
- **WHEN** the operator opens `GET /`
- **THEN** the page source includes marker-line drawing for the six canvases
  and does not reference an external annotation CDN

#### Scenario: Snapshot schema exposes markers
- **WHEN** `GET /api/snapshot` runs for a fixture with one `node_local` marker
- **THEN** the JSON body contains `markers` with that `reason_code` and `host`

### Requirement: Wrap PNG annotates the same markers
When matplotlib is available, wrap-time process PNGs and eth/TCP PNGs SHALL
draw a vertical line and a host/`reason_code` label at each marker `ts` that
falls inside that chart's sample time range. Markers outside the range MUST
be omitted. Missing matplotlib or missing markers MUST leave JSONL intact
and MUST NOT fail wrap.

#### Scenario: In-range marker draws on process PNG
- **WHEN** a process JSONL spans ts 1..10 and a `mpi_abort` marker has ts 5
- **THEN** the process plot path draws a vertical marker at ts 5

#### Scenario: Out-of-range marker is skipped
- **WHEN** a chart's samples span ts 1..10 and a marker has ts 50
- **THEN** that chart MUST NOT draw a vertical line for the marker

#### Scenario: No markers keeps JSONL and still plots
- **WHEN** wrap plots a run with series and no marker files
- **THEN** PNG generation still follows the existing optional-plot contract
  and JSONL remains
