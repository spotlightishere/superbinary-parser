import argparse
import pathlib

from fota_payload import FotaPayload
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
    # TODO(spotlightishere): implement LZMA stream decompression
    # write_payload("FOTA", fota.decompress())
    # print("Decompressed FOTA payload!")

    write_payload("FOTA.bin.sig", fota.unknown)
    write_payload("FOTA.bin.lzma", fota.compressed)
