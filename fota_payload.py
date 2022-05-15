from dataclasses import dataclass, field

import LZMAalone


@dataclass
class FotaPayload(object):
    """Simple wrapper to assist in decompressing/parsing a FOTA payload."""

    # Appears to involve two signatures and a version. Metadata, perhaps?
    unknown: bytes = field(repr=False)
    # LZMA compressed payload.
    compressed: bytes = field(repr=False)

    def __init__(self, data: bytes):
        # Our unknown payload is 0x29E in length.
        self.unknown = data[0:0x29E]

        # Our compressed payload starts at 0x1000 and goes to the end.
        self.compressed = data[0x1000:]

    def decompress(self) -> bytes:
        """Decompresses the LZMA-encoded payload."""
        # We need to manually parse the header because things are very broken otherwise.
        return LZMAalone.decompress(self.compressed)
