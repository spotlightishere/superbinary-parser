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
    "output_dir",
    help="The directory to save payloads to.",
    type=pathlib.Path,
)
parser.add_argument(
    "--extract-payloads",
    help="Whether to extract all payloads of this SuperBinary.",
    action=argparse.BooleanOptionalAction,
    default=True,
)
parser.add_argument(
    "--decompresss-fota",
    help="Whether to decompress the FOTA.",
    action=argparse.BooleanOptionalAction,
)
parser.add_argument(
    "--extract-rofs",
    "--extract-sounds",
    help="If set, extracts the ROFS partition to the output directory under 'files'.",
    type=argparse.BooleanOptionalAction,
)
args = parser.parse_args()
super_binary = SuperBinary(args.source)
print(super_binary)

# Ensure our payload directory can be written to.
payload_dir = args.output_dir
payload_dir.mkdir(parents=True, exist_ok=True)

# Write out payloads if desired.
if args.extract_payloads:
    for payload in super_binary.payloads:
        print(f"Saving {payload.get_tag()}...")
        print(payload)
        name = payload.get_tag() + ".bin"
        path = payload_dir / name
        # Write!
        with open(path, "wb") as f:
            f.write(payload.payload)

    # Lastly, write the SuperBinary plist.
    with open(payload_dir / "SuperBinary.plist", "wb") as f:
        f.write(super_binary.plist_data)
