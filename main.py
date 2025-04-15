import argparse
import os
import pathlib
import sys

from compressed_payload import decompress_payload_chunks
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
    "--use-tag-name",
    help="Whether to extract payloads via their tag name instead of full path.",
    action=argparse.BooleanOptionalAction,
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
if args.extract_rofs and not args.decompress_fota:
    print("Please ensure that --decompress-fota is specified.")
    exit(1)


super_binary = SuperBinary(args.source)

# Ensure our payload directory can be written to.
payload_dir = args.output_dir
payload_dir.mkdir(parents=True, exist_ok=True)


def write_payload(file_name: str, file_contents: bytes):
    file_path: pathlib.Path = payload_dir / file_name

    # In the case of fullpaths, we may need to make a parent directory first.
    file_path.parent.mkdir(parents=True, exist_ok=True)

    with open(file_path, "wb") as f:
        f.write(file_contents)


# Write out payloads if desired.
if args.extract_payloads:
    # Used to avoid conflicts in both tag names and fullpaths.
    seen_filenames: dict[str, int] = {}

    for payload in super_binary.payloads:
        tag_name = payload.get_tag()
        payload_name = payload.plist_metadata.long_name or "no long name"

        payload_filename: str
        if args.use_tag_name:
            payload_filename = f"{tag_name}.bin"
        else:
            # We want to leverage the payload's given filepath.
            # Ensure its parent directories exist.
            payload_filename = payload.plist_metadata.filepath

        # Sometimes, tags have multiple payloads, and filepaths conflict.
        # Let's append a number for every occurrence.
        seen_count = seen_filenames.get(payload_filename)
        print(seen_count)
        if seen_count is not None:
            # We have a tag! Increment its seen count.
            seen_filenames[payload_filename] += 1

            # Append the count at the end of the file.
            payload_filename = f"{payload_filename}.{seen_count}"
        else:
            seen_filenames[payload_filename] = 1

        print(f"Saving {tag_name} ({payload_name}) to {payload_filename}...")

        # Sometimes, this may be an absolute path.
        # For example, some filepaths start with `/Library` or `/tmp`.
        # Tags should (hopefully) never run in to this.
        #
        # Let's append `./` to the start to ensure relative resolution.
        payload_filename = f"./{payload_filename}"
        write_payload(payload_filename, payload.contents)

    # Lastly, write the SuperBinary plist.
    write_payload("SuperBinary.plist", super_binary.raw_plist_data)

if args.decompress_fota:
    # Ensure we have a payload of this type.
    fota_payload = super_binary.get_tag(b"FOTA")
    if not fota_payload:
        print("Missing FOTA payload!")
        exit(1)

    fota = FotaPayload(fota_payload.contents)
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
        rofs_partition = find_rofs(fota.segments)
        os.makedirs(payload_dir / "files", exist_ok=True)
        for file in rofs_partition.files:
            write_payload(f"files/{file.file_name}", file.contents)


if args.decompress_payload_contents:
    for payload in super_binary.payloads:
        # The metadata plist present at the end of the SuperBinary
        # defines what segments are compressed.
        # For our purpose, any compressed segment has a `compressed_chunk_size` that is not None.
        chunk_size = payload.plist_metadata.compressed_chunk_size
        if not chunk_size:
            continue

        # TODO(spotlightishere): This should function on platforms beyond macOS.
        assert (
            sys.platform == "darwin"
        ), "Decompression is not yet supported on this platform."


        print(f"Decompressing {payload.get_tag()}...")
        contents = decompress_payload_chunks(payload)
        write_payload(f"{payload.get_tag()}.decompressed.bin", contents)
