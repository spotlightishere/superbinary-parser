from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
import ctypes
import struct
import sys

# TODO(spotlightishere): Replace libcompression.dylib with a cross-platform implementation
libcompression = ctypes.CDLL("libcompression.dylib")

# TODO(spotlightishere): We should not depend on the chunk size always being 16,384.
# Instead, read this value from the SuperBinary plist.
STANDARD_BLOCK_SIZE = 16384

# Our header's length is 10 bytes in length.
COMPRESSED_HEADER_LENGTH = 10


class CompressionTypes(Enum):
    """Possible values for a payload's compression type."""

    # Simply copies data - no compression is applied.
    PASSTHROUGH = 0
    # Internally known as "LZBitmapFast2"
    LZBITMAPFAST = 1
    # Internally known as "LZBitmap2"
    LZBITMAP = 2
    LZ4 = 3

    def get_compression_algorithm(self) -> int:
        """Returns a usable value for compression algorithms with libcompression."""
        # TODO(spotlightishere): This should be removed once usage can be
        # migrated to a platform-agnostic library.
        if self == CompressionTypes.PASSTHROUGH:
            # This is a special, uncompressed type.
            #
            # If this is erroneously handled as compressed data,
            # libcompression should error elsewhere.
            return 0
        elif self == CompressionTypes.LZBITMAPFAST:
            # Undocumented compression type.
            # It's 0x100 less than its sibling, LZBITMAP.
            return 0x602
        elif self == CompressionTypes.LZBITMAP:
            # https://developer.apple.com/documentation/compression/compression_algorithm/compression_lzbitmap?language=objc
            return 0x702
        elif self == CompressionTypes.LZ4:
            # https://developer.apple.com/documentation/compression/compression_algorithm/compression_lz4?language=objc
            return 0x100
        else:
            raise AssertionError("Unknown compression type!")


@dataclass
class CompressedChunk(object):
    """Parses and decompresses a chunk of a compressed payload."""

    # Compression type - the only observed value is LZBitmapFast2.
    # (However, this appears to match with CoreUARP's handling of such.)
    raw_compression_type: int

    # Offset of this chunk within the decompressed file.
    # We can't use this.
    decompressed_offset: int

    # Amount of compressed data within this chunk.
    compressed_length: int

    # Size of uncompressed data this chunk produces.
    #
    # This should match the standard block size; if not,
    # this is the final chunk to be decompressed.
    decompressed_length: int

    # Our raw data to decompress.
    compressed_data: bytes = field(repr=False)

    def __init__(self, raw_data: BytesIO):
        # Parse the current chunk's metadata. This is seemingly always big endian.
        (
            raw_compression_type,
            self.decompressed_offset,
            self.compressed_length,
            self.decompressed_length,
        ) = struct.unpack_from(">HIHH", raw_data.read(COMPRESSED_HEADER_LENGTH))
        self.compression_type = CompressionTypes(raw_compression_type)

        # Passthrough chunks must have the same length for compressed and decompressed data.
        if self.compression_type == CompressionTypes.PASSTHROUGH:
            assert (
                self.compressed_length == self.decompressed_length
            ), "Invalid passthrough chunk lengths!"

        # Our raw data is immediately beyond our header.
        self.compressed_data = raw_data.read(self.compressed_length)

    def decompress(self) -> bytes:
        """Leverages libcompression from macOS to decompress contents."""
        # If this is passthrough, we simply return our "compressed" data's length.
        if self.compression_type == CompressionTypes.PASSTHROUGH:
            return self.compressed_data

        # TODO(spotlightishere): Replace libcompression.dylib with a cross-platform implementation
        compression_algorithm = self.compression_type.get_compression_algorithm()

        # Otherwise, decompresss!
        decompressed_buf = ctypes.create_string_buffer(self.decompressed_length)
        buffer_size = libcompression.compression_decode_buffer(
            decompressed_buf,
            self.decompressed_length,
            self.compressed_data,
            self.compressed_length,
            None,
            compression_algorithm,
        )
        return decompressed_buf[0:buffer_size]


def decompress_payload_chunks(raw_data: bytes) -> bytes:
    """Decompresses a compressed payload within a SuperBinary."""

    data = BytesIO(raw_data)
    decompressed_data = BytesIO()

    # We're not presented with the resulting size of this content.
    # As such, we'll need to iterate through this entire file, handling chunks as we go.
    while True:
        # Read and decompress the current chunk.
        current_chunk = CompressedChunk(data)
        decompressed = current_chunk.decompress()

        # Ensure we've fully decompressed this data as expected.
        expected_length = current_chunk.decompressed_length
        actual_length = len(decompressed)

        if expected_length != actual_length:
            # We need to step back by this current chunk's size in order to get its starting offset.
            chunk_offset = (
                data.tell() - current_chunk.compressed_length - COMPRESSED_HEADER_LENGTH
            )
            raise AssertionError(
                "Data did not fully decompress! "
                f"(chunk offset {chunk_offset}; expected {expected_length}, but only read {actual_length})"
            )

        decompressed_data.write(decompressed)

        # If we have a block size that decompresses to less than our
        # chunk size, then we've come to an end of chunks.
        if len(decompressed) != STANDARD_BLOCK_SIZE:
            break

    return decompressed_data.getbuffer()
