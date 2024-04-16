# `versol`

`versol` is a Python library that implements a generic dependency solver based
on the PubGrub algorithm.

This is alpha-quality software. Don't depend on it for anything important!


## Basic Usage

The `versol` package is small and easily discoverable. The main modules of
interest being:

- `versol.solve` exposes the generic `solve()` function.
- `versol.report` exposes a `generate_report` function that can be used to
  generate diagnostic reports when dependency resolution fails.
