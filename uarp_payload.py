import io
import struct
from dataclasses import dataclass, field


@dataclass
class UarpPayload(object):
    # The tag representing this payload, i.e. 'FOTA'.
    tag: bytes
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
    # The data represented by this payload.
    payload: bytes = field(repr=False)

    def __init__(self, metadata: bytes, data: io.BufferedReader):
        # Parse metadata.
        (
            metadata_tag_size,
            self.tag,
            self.major_version,
            self.minor_version,
            self.release_version,
            self.build_version,
            self.metadata_length,
            self.metadata_offset,
            self.payloads_offset,
            self.payloads_length,
        ) = struct.unpack_from(">I4sIIIIIIII", metadata)

        # Obtain our payload.
        data.seek(self.payloads_offset)
        self.payload = data.read(self.payloads_length)
        print(self.tag)

    def get_tag(self) -> str:
        """Returns a string with the given tag name."""
        return self.tag.decode("utf-8")
