# Tabular data (to do)

Design notes (from 2026-10-15) for reworking how PCOT handles tabular data. Nothing here is
implemented yet.

## Where things are now

- `Datum.TABLE` holds a `pcot.utils.table.Table`: an ordered dict of labelled rows, built up a cell at
  a time with `newRow()`/`add()`. It's produced by the spectrum and histogram nodes, `dq`/help/parse
  output and a few others, and `expr` can index into it (`Table.getByIndices`).
- All output (CSV, HTML, markdown, text) goes through `Table._printable()`, so float formatting is
  decided in one place - but it's decided by the table, not by whatever is writing it.
- The table type can't be serialised, so tables can't go in PARC files. The sink's
  *Save...* button saves them as CSV only, using `str(table)` - the same CSV that `pcotbatch` writes.
- Spectra are stored *as* tables, flattened to strings-and-floats with columns like `m640,s640,p640`
  (mean, SD, pixel count per band), so their uncertainty is only kept as an ordinary column.

### Float formatting

`Table._printable()` used `round(v, 5)`: five *decimal places*, not significant figures. Small values
were silently written as `0.0` (e.g. 1.23e-7), in both GUI and batch CSV output. An uncommitted
change (2026-10-15) makes it use the `sigfigs` config setting as real significant figures, but
never fewer digits than a value has before the decimal point (so 123456.789 is `123457`, not
`1.2346e+05`). The expected outputs of several graph and runner tests had to change with it.

It's held back because the rework below may replace it. If the rework happens, formatting should
move into the writers (see below) and this rule should go with it.

## Proposal: tabular views

Spectral data may get its own Datum type, and other types will probably be representable as tables
(calibration data, for example). Some of this data may be large. Rather than converting everything
into a `Table`, each type would provide **tabular views**: objects which present a Datum's data as
rows without copying it.

- A view is created from a Datum. Asking for a view of a Datum whose type doesn't support one throws.
- Nothing that writes or displays tables (CSV export, the sink, table widgets, batch outputs) needs
  to know about the underlying types - they all work through views.

### Design notes

- **Iteration:** use Python iteration (`__iter__`, ideally a generator) rather than a
  `hasNextRow()`/`getNextRow()` pair. Generators give lazy row production for free and callers just
  write `for row in view`; `hasNextRow()` is awkward to implement over a generator because it needs
  lookahead.
- **Row count may be unknown:** for large or lazily generated data, counting rows may mean producing
  them all. `getRowCount()` could return `None` when it isn't cheap. Streaming consumers like a CSV
  writer don't need it.
- **Columns up front:** column names - ideally with types and units - should be available before
  iterating. A CSV writer needs the header first, and a table widget needs columns before rows.
- **Typed cells, not strings:** cells should be real values. Formatting (significant figures etc.)
  then belongs to the writer, which fixes the float formatting problem above in one place rather
  than per table.
- **Values with uncertainty:** decide whether a cell can hold a `Value` (nominal, uncertainty, DQ).
  Either the view splits these into separate columns (as spectra do now with `m640,s640`) or it
  passes `Value`s through and lets the writer split them. Passing them through is probably better:
  consumers other than text writers then keep the uncertainty and DQ.
- **Random access for the GUI:** Qt table models request arbitrary rows as the user scrolls, so a
  forward-only iterator can't back a table widget showing large data. An optional `getRow(i)`,
  provided only by views which can do it cheaply, would cover that.
- **Opt-in per type, like serialisation:** a `Type.tabularView(d)` method which throws by default, and
  a `canTabulate()` (like `Type.canSerialise()`) so the UI can grey out options in advance - as the
  sink's Save button does for types it can't save. The Save dialog could then offer CSV for any type
  that can be tabulated, not just `Datum.TABLE`.
- **Several views of one type:** a type may provide more than one view. Calibration data could
  reasonably be several tables (e.g. per-filter coefficients and metadata). Views would need names,
  so callers can list and choose them.
- **Several views of one table:** a single underlying table may also be viewed in more than one way -
  for example a spectrum by ROI or by band (wide vs. long form), or a subset of its columns. So a view
  is a presentation of the data, not the data itself, and there's no single "the table" for a Datum.

### Migration

The current `Table` class could become one implementation among several: the `TABLE` type's view
would just wrap it. Existing nodes and `expr` indexing would keep working while other types move
over to views of their own.
