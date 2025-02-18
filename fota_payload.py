import io
import lzma
import struct
from dataclasses import dataclass, field
from enum import IntEnum


class FotaMetadataType(IntEnum):
    """Known metadata types within a FOTA payload. This is not exhaustive."""

    FORMAT_METADATA = 0x11
    SEGMENT_METADATA = 0x12
    FIRMWARE_VERSION = 0x13
    PARTITION_HASHES = 0x14
    CHIPSET_NAME = 0x20
    DESIGN_NAME = 0x21
    FLAG_UNKNOWN = 0xF0


@dataclass
class FotaUnknown:
    """An unknown TLV type."""

    contents: bytes


@dataclass
class FotaString:
    """A C string with a fixed length."""

    contents: str

    def __init__(self, binary_contents: bytes):
        self.contents = binary_contents.decode("utf-8")

    def __repr__(self):
        return self.contents


@dataclass
class FotaFormatMetadata(object):
    # Observed values have been 0x0102.
    # This may mean there's a u1 with value 2,
    # indicating two payloads,
    # or perhaps something entirely different.
    #
    # For ease, let's assume they're a u2,
    # and that there are only two payload segments.
    unknown: int = 0

    # The size of this metadata segment.
    # Observed values have been 0x1000 (4096 bytes).
    metadata_size: int = 0

    # The size of the compressed firmware segment.
    payload_size: int = 0

    def __init__(self, contents: io.BytesIO):
        (self.payload_offset, self.payload_length, self.unknown) = struct.unpack(
            "<HII", contents.read(10)
        )


@dataclass
class FotaSegment(object):
    # The offset of this segment within the payload.
    # This is within the total, decompressed FOTA format.
    # To access this segment within the decompressed format,
    # subtract the metadata size (e.g. 0x1000).
    payload_offset: int = 0

    # Length of this segment within the payload.
    payload_length: int = 0

    # Unknown.
    unknown: int = 0

    def __init__(self, contents: io.BytesIO):
        (self.payload_offset, self.payload_length, self.unknown) = struct.unpack(
            "<III", contents.read(12)
        )


@dataclass
class FotaSegmentArray(object):
    """Reads an array of FOTA segments."""

    segments: list[FotaSegment] = field(repr=False)

    def __init__(self, contents: io.BytesIO):
        self.segments = []

        segment_count = struct.unpack("<I", contents.read(4))[0]
        for _ in range(segment_count):
            current_segment = FotaSegment(contents)
            self.segments.append(current_segment)


@dataclass
class FotaHashes(object):
    """Reads an array of FOTA hashes."""

    hashes: list[bytes] = field(repr=False)

    def __init__(self, contents: io.BytesIO):
        self.hashes = []

        hash_count = struct.unpack("<I", contents.read(4))[0]
        for _ in range(hash_count):
            current_hash = contents.read(32)
            self.hashes.append(current_hash)


@dataclass
class FotaMetadata(object):
    """Parses the TLV format present within FOTA metadata."""

    # Possibly an RSA signature.
    signature: bytes = field(repr=False)

    # Segment information within the given payload.
    segments: list[FotaSegment]

    # All metadata in their raw, class format.
    # This includes metadata with values otherwise unknown.
    all_metadata: dict[FotaMetadataType, object]

    def __init__(self, binary_contents: bytes):
        # Initialize our list and dictionary fields.
        self.format_metadata = []
        self.segments = []
        self.all_metadata = {}

        # We begin with a 256-byte signature.
        data = io.BytesIO(binary_contents)
        self.signature = data.read(256)

        while True:
            # Following our signature, we have an array of TLV entries.
            # Directly proceeding them is padding filled with 0xFF.
            #
            # There appears to be no count of the TLV fields, so we simply
            # cease reading once we encounter a type of 0xFFFF.
            # (At worst, we'll fail with an exception.)
            (data_type, data_length) = struct.unpack_from("<HH", data.read(4))
            if data_type == 0xFFFF:
                # We've reached the end of possible TLV types.
                break
            data_contents = data.read(data_length)
            data_stream = io.BytesIO(data_contents)

            # We only handle a subset of known metadata types.
            current_object: object

            if data_type == FotaMetadataType.FORMAT_METADATA:
                current_object = FotaFormatMetadata(data_stream)
                self.format_metadata.append(current_object)
            elif data_type == FotaMetadataType.SEGMENT_METADATA:
                current_object = FotaSegmentArray(data_stream)
                self.segments = current_object.segments
            elif data_type == FotaMetadataType.FIRMWARE_VERSION:
                # This is a null-terminated string.
                # Some firmware versions pad this with 0xFF to be 64 bytes.
                # As such, we'll strip beyond the first null byte.
                null_pos = data_contents.index(b"\x00")
                current_object = FotaString(data_contents[0:null_pos])
            elif data_type == FotaMetadataType.PARTITION_HASHES:
                current_object = FotaHashes(data_stream)
            elif data_type == FotaMetadataType.CHIPSET_NAME:
                current_object = FotaString(data_contents)
            elif data_type == FotaMetadataType.DESIGN_NAME:
                current_object = FotaString(data_contents)
            else:
                # We'll use this as a placeholder object.
                current_object = FotaUnknown(data_contents)

            self.all_metadata[data_type] = current_object


@dataclass
class FotaPayload(object):
    """Simple wrapper to assist in decompressing/parsing a FOTA payload."""

    # The raw bytes for the metadata component of this payload.
    raw_metadata: bytes

    # Metadata for this FOTA payload.
    metadata: FotaMetadata

    # LZMA compressed payload.
    compressed: bytes = field(repr=False)

    # Decompressed LZMA payload.
    decompressed: bytes = field(repr=False)

    # Segments within.
    segments: list[bytes] = field(repr=False)

    def __init__(self, data: bytes):
        # Our metadata is 4096 bytes in length.
        # This may not be guaranteed, but appears to be consistent
        # across released firmware versions.
        #
        # TODO(spotlightishere): We may need to some day parse
        # FOTA payload metadata anyway, and go from there.
        self.raw_metadata = data[0:0x1000]
        self.metadata = FotaMetadata(self.raw_metadata)

        # Our compressed payload starts at 0x1000 and goes to the end.
        self.compressed = data[0x1000:]

        # Decompress our LZMA payload.
        self.decompressed = lzma.decompress(self.compressed)

        # Separate segments within.
        self.segments = []
        for segment in self.metadata.segments:
            # Each segment offset is 0x1000 ahead,
            # as the decompressed portions likely
            # overwrites the compressed portion in memory.
            segment_offset_start = segment.payload_offset - 0x1000
            segment_offset_end = segment_offset_start + segment.payload_length
            segment_contents = self.decompressed[
                segment_offset_start:segment_offset_end
            ]
            self.segments.append(segment_contents)
