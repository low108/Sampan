"""Execute the notebook from a clean slate and write the outputs back.

Clearing every output first is the whole point, and it is not tidiness. A run
that fails partway leaves earlier cells holding results from a previous version
of the code, and the notebook then shows two answers to the same question with
nothing marking either as stale. That happened: section 4 printed nine tools and
section 5 printed five, from the same object, because one output predated the
consolidation and was never overwritten.

Execution counts are the tell. In a clean run they ascend in document order; a
cell numbered 31 in a notebook with 27 code cells is left over from something
else. This resets them all to None first, so a partial run is visibly partial
rather than quietly mixed.

    uv run python notebooks/run_notebook.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import nbformat
from nbclient import NotebookClient

NOTEBOOK = Path(__file__).parent / "knowledge_base_flow.ipynb"


def main() -> int:
    nb = nbformat.read(NOTEBOOK, as_version=4)
    nbformat.validator.normalize(nb)

    for cell in nb.cells:
        if cell.cell_type == "code":
            cell.outputs = []
            cell.execution_count = None

    client = NotebookClient(
        nb,
        timeout=900,
        kernel_name="python3",
        resources={"metadata": {"path": str(NOTEBOOK.parent)}},
    )
    try:
        client.execute()
    except Exception as err:  # noqa: BLE001
        nbformat.write(nb, NOTEBOOK)
        print(f"FAILED: {type(err).__name__}", file=sys.stderr)
        print(str(err)[:2000], file=sys.stderr)
        return 1

    nbformat.write(nb, NOTEBOOK)

    code = [c for c in nb.cells if c.cell_type == "code"]
    counts = [c.execution_count for c in code]
    errors = [o for c in code for o in c.outputs if o.output_type == "error"]

    print(f"executed {len(code)} code cells, {len(errors)} errors")
    # Ascending counts prove one run produced every output on the page.
    print(f"execution order clean: {counts == sorted(counts)}")
    print(f"cells with output: {sum(1 for c in code if c.outputs)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
