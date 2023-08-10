from plist_unarchiver import SomewhatKeyedUnarchiver
from dataclasses import dataclass


@dataclass
class MetadataPlist(object):
    """A simple parser of the metadata plist embedded at the end of a SuperBinary.

    For now, its implementation simply obtains compressed payloads.
    It may be desirable to extend this in the future."""

    metadata: dict
    compressed_payload_tags: [(bytes, int)]

    def __init__(self, plist_data: bytes):
        unarchiver = SomewhatKeyedUnarchiver(plist_data)
        self.metadata = unarchiver.unarchive_root_object()
        self.compressed_payload_tags = []

        # Find all compressed payloads. Such payloads have
        # key "Payload Compression ChunkSize" underneath "Payload MetaData".
        payloads = self.metadata["SuperBinary Payloads"]
        for payload in payloads:
            if not "Payload MetaData" in payload:
                continue
            payload_metadata = payload["Payload MetaData"]
            payload_tag = bytes(payload["Payload 4CC"], "ascii")

            # Ensure we have a chunksize present.
            if not "Payload Compression ChunkSize" in payload_metadata:
                continue

            payload_chunksize = payload_metadata["Payload Compression ChunkSize"]
            self.compressed_payload_tags += [(payload_tag, payload_chunksize)]
