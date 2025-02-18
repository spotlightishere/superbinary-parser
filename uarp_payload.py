import io
import struct
from dataclasses import dataclass, field
from metadata_plist import UarpMetadata


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
    # Binary metadata held by the current payload.
    # Note that, in some firmware, it may be empty.
    metadata: bytes = field(repr=False)
    # Metadata specified for this payload within the SuperBinary plist.
    plist_metadata: UarpMetadata
    # The data represented by this payload.
    contents: bytes = field(repr=False)

    def __init__(
        self,
        header: bytes,
        plist_tuple: (bytes, UarpMetadata),
        data: io.BufferedReader,
    ):
        # Parse the metadata within header.
        (
            metadata_tag_size,
            self.tag,
            self.major_version,
            self.minor_version,
            self.release_version,
            self.build_version,
            self.metadata_offset,
            self.metadata_length,
            self.payloads_offset,
            self.payloads_length,
        ) = struct.unpack_from(">I4sIIIIIIII", header)

        # Verify that our SuperBinary plist's tag
        # matches the obtained one above.
        (plist_tag, plist_metadata) = plist_tuple
        assert plist_tag == self.tag, "Mismatched tag between payload and metadata!"
        self.plist_metadata = plist_metadata

        # Obtain our metadata and payload.
        data.seek(self.metadata_offset)
        self.metadata = data.read(self.metadata_length)

        data.seek(self.payloads_offset)
        self.contents = data.read(self.payloads_length)

    def get_tag(self) -> str:
        """Returns a string with the given tag name."""
        return self.tag.decode("utf-8")
