import io
import struct
from dataclasses import dataclass, field
from typing import Optional

from metadata_plist import MetadataPlist, UarpMetadata
from uarp_payload import UarpPayload


@dataclass
class SuperBinary(object):
    """Simple wrapper to assist in parsing SuperBinary contents."""

    # Only known version is 2.
    header_version: int
    # The length of the SuperBinary header (not including others).
    header_length: int
    # The size this SuperBinary payload spans.
    # Note that data may trail (i.e. the SuperBinary plist).
    binary_size: int
    # i.e. 100 in '100.7916.1052884864.1'.
    major_version: int
    # i.e. 7916 in '100.7916.1052884864.1'.
    minor_version: int
    # i.e. 1052884864 in '100.7916.1052884864.1'.
    release_version: int
    # i.e. 1 in '100.7916.1052884864.1'.
    build_version: int
    # Metadata size.
    metadata_length: int
    # Observed to be zero.
    metadata_offset: int
    # Payloads length
    row_length: int
    # Payloads offset
    row_offset: int

    # Payloads available within this binary.
    payloads: list[UarpPayload]
    # Trailing data past payload (i.e. SuperBinary plist).
    raw_plist_data: bytes = field(repr=False)
    # The unarchived, top-level SuperBinary plist.
    metadata: MetadataPlist

    def __init__(self, data: io.BufferedReader):
        self.payloads = []

        # Ensure the version and size initially to ensure this file is correct.
        self.header_version, self.header_length = struct.unpack_from(
            ">II", data.read(8)
        )
        assert self.header_version in [2, 3], "Unknown version of SuperBinary!"
        assert self.header_length == 0x2C, "Invalid header length for version!"

        # Load the remainder of the header.
        (
            self.binary_size,
            self.major_version,
            self.minor_version,
            self.release_version,
            self.build_version,
        ) = struct.unpack_from(">IIIII", data.read(20))

        # Next, load offsets and length information.
        (
            self.metadata_offset,
            self.metadata_length,
            self.row_offset,
            self.row_length,
        ) = struct.unpack_from(">IIII", data.read(16))

        # At this point, we have gone past the SuperBinary header (0x2c).
        # Our binary plist is at the end of our payload (`binary_size`).
        # Let's read it, and then jump back.
        data.seek(self.binary_size)
        self.raw_plist_data = data.read()

        # Unarchive the SuperBinary plist.
        self.metadata = MetadataPlist(self.raw_plist_data)

        # Jump back to where we left off, and finally extract actual payload metadata.
        data.seek(0x2C)
        # The observed tag size is 0x28, so we will assume that.
        # Please make an issue (or a PR) to change this logic in the future!
        queried_data = struct.unpack_from(">I", data.peek(4))
        metadata_tag_size = queried_data[0]
        assert metadata_tag_size == 0x28, "Unknown metadata tag size!"
        row_count = self.row_length // metadata_tag_size

        # TODO(spotlightishere): Is there any condition
        # in which the length of the payload metadata array
        # will not match the count of actual payloads?
        assert row_count == len(
            self.metadata.payload_tags
        ), "Mismatched payload count between binary and metadata!"

        # Obtain the metadata for all possible payloads.
        for payload_num in range(row_count):
            # Determine the metadata offset for this payload.
            offset = self.header_length + (payload_num * metadata_tag_size)
            data.seek(offset)
            payload_metadata = data.read(metadata_tag_size)

            # This is a tuple with [tag, UarpMetadata].
            plist_tuple = self.metadata.payload_tags[payload_num]
            payload = UarpPayload(payload_metadata, plist_tuple, data)
            self.payloads.append(payload)

    def get_tag(self, tag: bytes) -> Optional[UarpPayload]:
        """Returns the payload for the given tag. Returns None if not present."""
        assert len(tag) == 4, "Invalid 4CC/magic passed!"
        for payload in self.payloads:
            if payload.tag == tag:
                return payload
        return None
