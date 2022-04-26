import io
import struct
from dataclasses import dataclass, field

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
    payload_size: int
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
    payloads_length: int
    # Payloads offset
    payloads_offset: int

    # Payloads available within this binary.
    payloads: list[UarpPayload]
    # Trailing data past payload (i.e. SuperBinary plist).
    plist_data: bytes = field(repr=False)

    def __init__(self, data: io.BufferedReader):
        self.payloads = []

        # Ensure the version and size initially to ensure this file is correct.
        self.header_version, self.header_length = struct.unpack_from(
            ">II", data.read(8)
        )
        assert self.header_version == 2, "Unknown version of SuperBinary!"
        assert self.header_length == 0x2C, "Invalid header length for version!"

        # Load the remainder of the header.
        (
            self.payload_size,
            self.major_version,
            self.minor_version,
            self.release_version,
            self.build_version,
        ) = struct.unpack_from(">IIIII", data.read(20))

        # Next, load offsets and length information.
        (
            self.metadata_offset,
            self.metadata_length,
            self.payloads_offset,
            self.payloads_length,
        ) = struct.unpack_from(">IIII", data.read(16))

        # Finally, extract actual payload metadata.
        # At this point, we have gone past the SuperBinary header (0x2c).
        # The observed tag size is 0x28, so we will assume that.
        # Please make an issue (or a PR) to change this logic in the future!
        queried_data = struct.unpack_from(">I", data.peek(4))
        metadata_tag_size = queried_data[0]
        assert metadata_tag_size == 0x28, "Unknown metadata tag size!"
        payload_count = self.payloads_length // metadata_tag_size

        # Obtain all possible payloads.
        for payload_num in range(payload_count):
            # Determine the metadata offset for this payload.
            offset = self.header_length + (payload_num * metadata_tag_size)
            data.seek(offset)
            payload_metadata = data.read(metadata_tag_size)
            payload = UarpPayload(payload_metadata, data)
            self.payloads.append(payload)

        # Lastly, take our ending plist.
        # Our payload size should be adequate.
        data.seek(self.payload_size)
        self.plist_data = data.read()

    def get_tag(self, tag: bytes) -> [UarpPayload, None]:
        """Returns the payload for the given tag. Returns None if not present."""
        assert len(tag) == 4, "Invalid 4CC/magic passed!"
        for payload in self.payloads:
            if payload.tag == tag:
                return payload
        return None
