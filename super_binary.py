import io
import struct
from dataclasses import dataclass


@dataclass
class SuperBinary(object):
    """Simple wrapper to assist in parsing SuperBinary contents."""

    # Only known version is 2.
    header_version: int
    # The size of the SuperBinary header (not including others).
    header_size: int
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
    # Metadata size. Must match that of header + payloads metadata.
    metadata_length: int
    # Observed to be zero.
    metadata_offset: int
    # Payloads length
    payloads_length: int
    # Payloads offset
    payloads_offset: int

    def __init__(self, data: io.BufferedReader):
        # Ensure the version and size initially to ensure this file is correct.
        self.header_version, self.header_size = struct.unpack_from(">II", data.read(8))
        assert self.header_version == 2, "Unknown version of SuperBinary!"
        assert self.header_size == 0x2C, "Invalid header size for version!"

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
            self.metadata_length,
            self.metadata_offset,
            self.payloads_length,
            self.payloads_offset,
        ) = struct.unpack_from(">IIII", data.read(16))
        assert self.metadata_offset == 0, "Invalid metadata offset!"


@dataclass
class UarpPayload(object):
    # i.e. 100 in '100.7916.1052884864.1'.
    major_version: int
    # i.e. 7916 in '100.7916.1052884864.1'.
    minor_version: int
    # i.e. 1052884864 in '100.7916.1052884864.1'.
    release_version: int
    # i.e. 1 in '100.7916.1052884864.1'.
    build_version: int
