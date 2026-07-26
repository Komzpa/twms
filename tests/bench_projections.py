"""Manual projection micro-benchmarks.

Run with:

    python tests/bench_projections.py

This intentionally is not named ``test_*.py`` so normal unittest discovery stays
fast and deterministic.
"""

import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from twms import projections


ITERATIONS = 100_000
MINSK_LON_LAT = (27.6, 53.2)
MINSK_3857 = (3072417.9458943508, 7020078.5326420991)
MINSK_3395 = (3072417.9458943508, 6985840.123947986)


def timed(label, func):
    start = time.perf_counter()
    value = None
    for _ in range(ITERATIONS):
        value = func()
    elapsed = time.perf_counter() - start
    print("%-28s %.3fs %r" % (label, elapsed, value))


def main():
    pr_4326 = projections.projs["EPSG:4326"]["proj"]
    pr_3857 = projections.projs["EPSG:3857"]["proj"]
    pr_3395 = projections.projs["EPSG:3395"]["proj"]
    has_pyproj = hasattr(projections.pyproj, "Transformer")
    transform_3857_to_4326 = projections._pyproj_transformer(pr_3857, pr_4326)
    transform_3395_to_4326 = projections._pyproj_transformer(pr_3395, pr_4326)
    transform_4326_to_3857 = projections._pyproj_transformer(pr_4326, pr_3857)
    transform_4326_to_3395 = projections._pyproj_transformer(pr_4326, pr_3395)

    timed(
        "pure 3857 -> 4326",
        lambda: projections._c3857t4326(None, None, MINSK_3857[0], MINSK_3857[1]),
    )
    timed(
        "wrapped 3857 -> 4326",
        lambda: projections.to4326(MINSK_3857, "EPSG:3857"),
    )
    if has_pyproj:
        timed(
            "pyproj helper 3857 -> 4326",
            lambda: transform_3857_to_4326(
                pr_3857, pr_4326, MINSK_3857[0], MINSK_3857[1]
            ),
        )

    timed(
        "pure 3395 -> 4326",
        lambda: projections._c3395t4326(None, None, MINSK_3395[0], MINSK_3395[1]),
    )
    timed(
        "wrapped 3395 -> 4326",
        lambda: projections.to4326(MINSK_3395, "EPSG:3395"),
    )
    if has_pyproj:
        timed(
            "pyproj helper 3395 -> 4326",
            lambda: transform_3395_to_4326(
                pr_3395, pr_4326, MINSK_3395[0], MINSK_3395[1]
            ),
        )

    timed(
        "pure 4326 -> 3857",
        lambda: projections._c4326t3857(None, None, MINSK_LON_LAT[0], MINSK_LON_LAT[1]),
    )
    timed(
        "wrapped 4326 -> 3857",
        lambda: projections.from4326(MINSK_LON_LAT, "EPSG:3857"),
    )
    if has_pyproj:
        timed(
            "pyproj helper 4326 -> 3857",
            lambda: transform_4326_to_3857(
                pr_4326, pr_3857, MINSK_LON_LAT[0], MINSK_LON_LAT[1]
            ),
        )

    timed(
        "pure 4326 -> 3395",
        lambda: projections._c4326t3395(None, None, MINSK_LON_LAT[0], MINSK_LON_LAT[1]),
    )
    timed(
        "wrapped 4326 -> 3395",
        lambda: projections.from4326(MINSK_LON_LAT, "EPSG:3395"),
    )
    if has_pyproj:
        timed(
            "pyproj helper 4326 -> 3395",
            lambda: transform_4326_to_3395(
                pr_4326, pr_3395, MINSK_LON_LAT[0], MINSK_LON_LAT[1]
            ),
        )


if __name__ == "__main__":
    main()
