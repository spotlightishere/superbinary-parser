import argparse
import os
import pathlib
import sys

from compressed_payload import decompress_payload_chunks
from fota_payload import FotaPayload
from metadata_plist import MetadataPlist
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
parser.add_argument(
    "--decompress-payload-contents",
    help="Whether to decompress payload contents in particular types of SuperBinaries.",
    action=argparse.BooleanOptionalAction,
    default=True,
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
    seen_tags: dict[str, int] = dict()
    for payload in super_binary.payloads:
        # Some tags may have duplicate payloads. Let's append a number for every occurrence.
        tag_name = payload.get_tag()
        tag_was_seen = False
        if seen_tags.get(tag_name) is not None:
            # We have a tag! Increment its seen count.
            seen_tags[tag_name] += 1
            tag_was_seen = True
        else:
            seen_tags[tag_name] = 0

        payload_name = payload.plist_metadata.long_name or "no long name"
        print(f"Saving {tag_name} ({payload_name})...")

        if tag_was_seen:
            # e.g. CHFW_1.bin
            seen_count = seen_tags[tag_name]
            payload_filename = f"{tag_name}_{seen_count}.bin"
        else:
            # e.g. CHFW.bin
            payload_filename = f"{tag_name}.bin"
        write_payload(payload_filename, payload.payload)

    # Lastly, write the SuperBinary plist.
    write_payload("SuperBinary.plist", super_binary.raw_plist_data)

if args.decompress_fota:
    # Ensure we have a payload of this type.
    fota_payload = super_binary.get_tag(b"FOTA")
    if not fota_payload:
        print("Missing FOTA payload!")
        exit(1)

    fota = FotaPayload(fota_payload.payload)
    write_payload("FOTA.bin.lzma", fota.compressed)

    # Decompress payload.
    write_payload("FOTA", fota.decompressed)

    # Separate segments within.
    os.makedirs(payload_dir / "segments", exist_ok=True)
    for i, segment_contents in enumerate(fota.segments):
        # Each segment offset is 0x1000 ahead
        # as the decompressed portions likely
        # overwrites the compressed portion in memory.
        write_payload(f"segments/{i}.bin", segment_contents)

    print("Extracted FOTA payload!")

if args.extract_rofs:
    if not args.decompress_fota:
        print("Please ensure that --decompress-fota is specified.")
        exit(1)

    # TODO(spotlightishere): properly determine ROFS location from data
    rofs_partition = find_rofs(fota.segments)
    os.makedirs(payload_dir / "files", exist_ok=True)
    for file in rofs_partition.files:
        write_payload(f"files/{file.file_name}", file.contents)

if args.decompress_payload_contents:
    # TODO(spotlightishere): This should function on platforms beyond macOS.
    assert (
        sys.platform == "darwin"
    ), "Decompression is not yet supported on this platform."

    for payload in super_binary.payloads:
        # The metadata plist present at the end of the SuperBinary
        # defines what segments are compressed.
        # For our purpose, any compressed segment has a `compressed_chunk_size` that is not None.
        chunk_size = payload.plist_metadata.compressed_chunk_size
        if not chunk_size:
            continue

        print(f"Decompressing {payload.get_tag()}...")
        contents = decompress_payload_chunks(payload)
        write_payload(f"{payload.get_tag()}.decompressed.bin", contents)
