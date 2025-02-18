from typing import Union, Optional

from plist_unarchiver import SomewhatKeyedUnarchiver
from dataclasses import dataclass


@dataclass
class UarpMetadata:
    # The raw dictionary of metadata available at a top level.
    # There are many keys we do not care about,
    # such as "Payload Certificate", "Payload Signature", etc.
    all_metadata: dict

    # The given "Payload Filepath" for this payload, typically
    # either a direct filename, or the build path.
    # Three prefixes have been observed:
    #  - usr/local/standalone/firmware/[...]
    #  - /Library/Caches/com.apple.xbs/[...]
    #  - /tmp/[...]
    filepath: str

    # The specified "Payload Long Name" for this payload.
    # This may not be present in all payloads.
    long_name: Optional[str]

    # A dictionary of other metadata on this payload under "Payload MetaData".
    # Consider the following examples of possible keys:
    #  - Payload Compression Algorithm, a string (e.g. LZBitmapFast2)
    #  - Compose Measured Payloads, an array of personalization options
    #  - Urgent Update, a boolean value
    #
    # These correspond to the dictionary of options present
    # within the top-level key "MetaData Values".
    payload_metadata: Union[str, dict, bool]

    # If this payload is compressed, this is the
    # raw chunk size of this compressed contents.
    # If the payload is not, this is None.
    compressed_chunk_size: Optional[int] = None

    def __init__(self, metadata: dict):
        self.all_metadata = metadata
        self.filepath = metadata.get("Payload Filepath")
        self.long_name = metadata.get("Payload Long Name")
        self.payload_metadata = metadata.get("Payload MetaData")

        if self.payload_metadata:
            chunk_size = self.payload_metadata.get("Payload Compression ChunkSize")
            self.compressed_chunk_size = chunk_size


@dataclass
class MetadataPlist(object):
    """A simple parser of the metadata plist embedded at the end of a SuperBinary.

    For now, its implementation simply obtains compressed payloads.
    It may be desirable to extend this in the future."""

    # The raw, unarchived metadata.
    all_metadata: dict

    # Metadata for all payloads.
    payload_tags: [(bytes, UarpMetadata)]

    def __init__(self, plist_data: bytes):
        unarchiver = SomewhatKeyedUnarchiver(plist_data)
        self.all_metadata = unarchiver.unarchive_root_object()
        self.payload_tags = []

        # Extract metadata for all payloads.
        # Some compressed payloads have the special key
        # "Payload Compression ChunkSize" within "Payload MetaData".
        payloads = self.all_metadata["SuperBinary Payloads"]
        for current_payload in payloads:
            payload_tag = bytes(current_payload["Payload 4CC"], "ascii")
            payload_metadata = UarpMetadata(current_payload)

            self.payload_tags.append((payload_tag, payload_metadata))
