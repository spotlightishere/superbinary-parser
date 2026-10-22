import io
import struct
from collections import defaultdict, deque
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
    # The size of every section's metadata entry in binary form.
    # Note that this is also mirrored to the property list.
    section_metadata_length: int
    # Observed to be zero.
    section_metadata_offset: int
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
        assert self.header_version in [2, 3, 4], "Unknown version of SuperBinary!"
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
            self.section_metadata_offset,
            self.section_metadata_length,
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

        # Binary row indices are used by metadata references.
        row_size = 0x28
        if self.row_length % row_size:
            raise ValueError("Payload table length is not a multiple of 40")
        if (self.row_offset < self.header_length
                or self.row_offset + self.row_length > self.binary_size):
            raise ValueError("Payload table is outside the SuperBinary")

        metadata_by_tag = defaultdict(deque)
        for tag, metadata in self.metadata.payload_tags:
            metadata_by_tag[tag].append(metadata)

        for row_index in range(self.row_length // row_size):
            data.seek(self.row_offset + row_index * row_size)
            header = data.read(row_size)
            if len(header) != row_size:
                raise ValueError(f"Truncated payload row {row_index}")
            fields = struct.unpack(">I4s8I", header)
            size, tag = fields[:2]
            if size != row_size:
                raise ValueError(f"Unknown payload header size in row {row_index}")
            for offset, length in ((fields[6], fields[7]), (fields[8], fields[9])):
                if offset + length > self.binary_size:
                    raise ValueError(f"Payload row {row_index} extends outside the SuperBinary")

            if metadata_by_tag[tag]:
                metadata = metadata_by_tag[tag].popleft()
            elif tag == b"CHDR" or (tag == b"PMAP" and self.header_version == 4):
                metadata = UarpMetadata({
                    "Payload Filepath": (
                        f"CHDR-{row_index}.bin" if tag == b"CHDR" else "PMAP.plist"
                    ),
                    "Payload Long Name": (
                        "Compressed chunk headers" if tag == b"CHDR"
                        else "Personalization Mapping"
                    ),
                    "Payload MetaData": {},
                })
            else:
                raise ValueError(f"Missing plist metadata for payload row {row_index} ({tag!r})")

            payload = UarpPayload(header, (tag, metadata), data)
            if (len(payload.metadata) != payload.metadata_length
                    or len(payload.contents) != payload.payloads_length):
                raise ValueError(f"Truncated data for payload row {row_index}")
            self.payloads.append(payload)

        unmatched = [tag for tag, entries in metadata_by_tag.items() if entries]
        if unmatched:
            raise ValueError(f"Plist metadata has no matching binary rows: {unmatched!r}")

    def get_tag(self, tag: bytes) -> Optional[UarpPayload]:
        """Returns the payload for the given tag. Returns None if not present."""
        assert len(tag) == 4, "Invalid 4CC/magic passed!"
        for payload in self.payloads:
            if payload.tag == tag:
                return payload
        return None
