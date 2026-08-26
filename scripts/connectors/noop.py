#!/usr/bin/env python3
# scripts/connectors/noop.py
"""
noop.py -- Accept one value, print it, exit 0. The honest placeholder.

WHY THIS FILE EXISTS. walk.py's schema requires every stop to name a
connector script. public_walk.yaml answered that requirement with
scripts/walk.py plus argv ["{harvested}"] -- a command that exits 2,
because walk.py declares --trail and --value and no positional at all.
walk_cartridge then lifts that path into the sealed manifest, where
mother_cat._announce_consent prints it to a human under the label "names
as runnable", in the one artifact a rider reads BEFORE deciding to ride.

VALIDATION PASSING IS NOT EXECUTION PASSING. walk.py checks that the named
file EXISTS and that {harvested} appears exactly once. Nothing anywhere
checks that the script accepts the argv it will be handed. So the label was
false while every gate reported green.

THE CURE IS A TRUE SENTENCE, NOT A VAGUER LABEL. This file exists IN ORDER
to be a no-op. It accepts exactly one positional, prints what it received,
and exits 0. A trail naming it is telling the truth.

WHY NOT MAKE `connector` OPTIONAL INSTEAD. That was the other candidate and
it is the bigger change: it forks _exact a second time and makes
_derive_consent_surface's output shape depend on trail content, in the one
artifact whose whole value is being uniform enough for a human to read at a
glance. Fifteen lines of real file is cheaper than a second optional field.

DELIBERATELY ABSENT: a --check, a wallet slot, and a row in the `sources`
roster. This reaches nothing outside the machine and holds no credential,
so a green row for it would be a green row for nothing.
"""
import argparse


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Accept one harvested value, print it, and exit 0."
    )
    parser.add_argument(
        "value",
        help="the harvested value a trail passes in place of {harvested}",
    )
    args = parser.parse_args(argv)
    print("noop connector received: " + args.value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
