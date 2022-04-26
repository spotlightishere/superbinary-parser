import argparse
import pathlib

from super_binary import SuperBinary

parser = argparse.ArgumentParser(
    description="Extracts a FOTA within a SuperBinary container."
)
parser.add_argument(
    "source",
    help='Path to the SuperBinary. Typically called "FirmwareUpdate.uarp".',
    type=argparse.FileType("rb"),
)
parser.add_argument(
    "--extract-payload",
    help="The path to save the extract payload/files to.",
    type=argparse.FileType("w"),
)
parser.add_argument(
    "--extract-rofs",
    "--extract-sounds",
    help="If set, extracts the ROFS partition to the given destination.",
    type=pathlib.Path,
)
args = parser.parse_args()
uarp = SuperBinary(args.source)
print(uarp)
