from dataclasses import dataclass, field
from enum import Enum
from io import BytesIO
import ctypes
import struct
import sys

from uarp_payload import UarpPayload

# TODO(spotlightishere): Replace libcompression.dylib with a cross-platform implementation
if sys.platform == "darwin":
    try:
        libcompression = ctypes.CDLL("libcompression.dylib")
    except OSError:
        libcompression = None
else:
    # For now, we cannot use it on non-darwin platforms.
    libcompression = None

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


def decompress_lzbitmap_fast(src: bytes, dst_len: int) -> bytes:
    """Decompresses Apple's LZBitmapFast2 algorithm (libcompression algorithm 0x602).

    Each block emits up to 128 bytes (16 groups of 8 bytes).
    Format of each block:
      - 32-bit header (little endian):
          low 16 bits: literal_mask (1 bit per group indicating if literal flags byte exists)
          high 16 bits: distance_mask (1 bit per group indicating if uint16 distance exists)
      - Uncompressed block special case:
          If literal_mask == 0xFFFF and 5th byte == 0x00:
              distance_mask is length to copy; if 0, marks end of stream.
      - Compressed block:
          popcount(literal_mask) bytes of group literal masks (1 byte per set bit)
          popcount(distance_mask) uint16_le distance words (1 word per set bit)
          literal stream follows
    """
    dst = bytearray()
    src_idx = 0
    distance = 8
    src_len = len(src)

    while len(dst) < dst_len and src_idx < src_len:
        if src_idx + 4 > src_len:
            break

        header = struct.unpack_from("<I", src, src_idx)[0]
        literal_mask = header & 0xFFFF
        distance_mask = (header >> 16) & 0xFFFF

        # Check for uncompressed block:
        # Literal mask is 0xFFFF and 5th byte is 0x00.
        if literal_mask == 0xFFFF and src_idx + 5 <= src_len and src[src_idx + 4] == 0:
            copy_len = distance_mask
            if copy_len == 0:
                # End of stream marker
                break
            src_idx += 5
            to_copy = min(copy_len, dst_len - len(dst))
            dst.extend(src[src_idx : src_idx + to_copy])
            src_idx += copy_len
            continue

        src_idx += 4

        # Compressed block (produces up to 128 bytes: 16 groups of 8 bytes)
        # 1. Read literal masks (1 byte per set bit in literal_mask)
        n_lit_masks = literal_mask.bit_count()
        lit_masks = src[src_idx : src_idx + n_lit_masks]
        src_idx += n_lit_masks

        # 2. Read distances (uint16_le per set bit in distance_mask)
        n_dists = distance_mask.bit_count()
        dist_bytes = src[src_idx : src_idx + n_dists * 2]
        src_idx += n_dists * 2
        dists = struct.unpack_from(f"<{n_dists}H", dist_bytes) if n_dists else ()

        lit_mask_idx = 0
        dist_idx = 0

        for g in range(16):
            if len(dst) >= dst_len:
                break

            if distance_mask & (1 << g):
                distance = dists[dist_idx]
                dist_idx += 1

            if literal_mask & (1 << g):
                byte_mask = lit_masks[lit_mask_idx]
                lit_mask_idx += 1
            else:
                byte_mask = 0

            for b in range(8):
                if len(dst) >= dst_len:
                    break

                if byte_mask & (1 << b):
                    # Literal byte
                    dst.append(src[src_idx])
                    src_idx += 1
                else:
                    # Match byte from past output
                    if distance > len(dst):
                        raise ValueError(
                            f"Invalid match distance: {distance} > {len(dst)}"
                        )
                    dst.append(dst[-distance])

    return bytes(dst)


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
    # May be smaller than the configured block size. Payload length, rather
    # than a short chunk, determines the end of the stream.
    decompressed_length: int

    # Our raw data to decompress.
    compressed_data: bytes = field(repr=False)

    def __init__(self, raw_data: BytesIO):
        # Packed, big-endian uint16/uint32/uint16/uint16 fields.
        header = raw_data.read(COMPRESSED_HEADER_LENGTH)
        if len(header) != COMPRESSED_HEADER_LENGTH:
            raise ValueError("Truncated compression chunk header")
        (
            raw_compression_type,
            self.decompressed_offset,
            self.compressed_length,
            self.decompressed_length,
        ) = struct.unpack(">HIHH", header)
        self.compression_type = CompressionTypes(raw_compression_type)

        # Passthrough chunks must have the same length for compressed and decompressed data.
        if self.compression_type == CompressionTypes.PASSTHROUGH:
            assert (
                self.compressed_length == self.decompressed_length
            ), "Invalid passthrough chunk lengths!"

        # Our raw data is immediately beyond our header.
        self.compressed_data = raw_data.read(self.compressed_length)
        if len(self.compressed_data) != self.compressed_length:
            raise ValueError("Truncated compressed chunk data")

    def decompress(self) -> bytes:
        """Leverages libcompression from macOS or native fallback to decompress contents."""
        # If this is passthrough, we simply return our "compressed" data's length.
        if self.compression_type == CompressionTypes.PASSTHROUGH:
            return self.compressed_data

        if self.compression_type == CompressionTypes.LZBITMAPFAST:
            if libcompression is not None:
                try:
                    decompressed_buf = ctypes.create_string_buffer(self.decompressed_length)
                    buffer_size = libcompression.compression_decode_buffer(
                        decompressed_buf,
                        self.decompressed_length,
                        self.compressed_data,
                        self.compressed_length,
                        None,
                        self.compression_type.get_compression_algorithm(),
                    )
                    if buffer_size > 0:
                        return decompressed_buf[0:buffer_size]
                except Exception:
                    pass
            return decompress_lzbitmap_fast(self.compressed_data, self.decompressed_length)

        # Otherwise, decompress via libcompression!
        if libcompression is not None:
            compression_algorithm = self.compression_type.get_compression_algorithm()
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

        raise NotImplementedError(
            f"Decompression for {self.compression_type.name} is not yet supported without libcompression."
        )


def decompress_payload_chunks(payload: UarpPayload) -> bytes:
    """Decompresses a compressed payload within a SuperBinary."""

    data = BytesIO(payload.contents)
    decompressed_data = BytesIO()

    # We're not presented with the resulting size of this content.
    # As such, we'll need to iterate through this entire file, handling chunks as we go.
    while data.tell() < len(payload.contents):
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

    return decompressed_data.getvalue()
