import argparse
import os
import pathlib

from fota_payload import FotaPayload
from rofs import find_rofs
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
    "--decompress-fota",
    help="Whether to decompress the FOTA.",
    action=argparse.BooleanOptionalAction,
)
parser.add_argument(
    "--extract-rofs",
    help="Whether to extract the ROFS partition to the output directory.",
    action=argparse.BooleanOptionalAction,
)
args = parser.parse_args()
super_binary = SuperBinary(args.source)

# Ensure our payload directory can be written to.
payload_dir = args.output_dir
payload_dir.mkdir(parents=True, exist_ok=True)


def write_payload(file_name: str, contents: bytes):
    file_path = payload_dir / file_name
    with open(file_path, "wb") as f:
        f.write(contents)


# Write out payloads if desired.
if args.extract_payloads:
    for payload in super_binary.payloads:
        print(f"Saving {payload.get_tag()}...")
        write_payload(payload.get_tag() + ".bin", payload.payload)

    # Lastly, write the SuperBinary plist.
    write_payload("SuperBinary.plist", super_binary.plist_data)

if args.decompress_fota:
    # Ensure we have a payload of this type.
    fota_payload = super_binary.get_tag(b"FOTA")
    if not fota_payload:
        print("Missing FOTA payload!")
        exit(1)

    fota = FotaPayload(fota_payload.payload)
    write_payload("FOTA.bin.sig", fota.unknown)
    write_payload("FOTA.bin.lzma", fota.compressed)

    # Decompress payload.
    fota_contents = fota.decompress()
    write_payload("FOTA", fota_contents)
    print("Decompressed FOTA payload!")

if args.extract_rofs:
    if not args.decompress_fota:
        print("Please ensure that --decompress-fota is specified.")
        exit(1)

    # TODO(spotlightishere): properly determine ROFS location from data
    rofs_partition = find_rofs(fota_contents)
    os.makedirs(payload_dir/"files", exist_ok=True)
    for file in rofs_partition.files:
        write_payload(f"files/{file.file_name}", file.contents)
