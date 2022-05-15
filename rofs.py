import struct
from dataclasses import dataclass, field
from io import BytesIO


@dataclass
class ROFSFile(object):
    """A file within a ROFS partition."""

    file_name: str
    contents: bytes = field(repr=False)


class ROFS(object):
    """Simple class to parse contents within a ROFS partition."""
    files: [ROFSFile] = []

    def __init__(self, passed_data: bytes):
        # Create a buffer we can read against.
        data = BytesIO(passed_data)

        # Ensure the header is correct.
        magic, length_one, length_two, file_count = struct.unpack_from(
            "<4sIII", data.read(16)
        )
        assert magic == b"ROFS", "Invalid ROFS magic!"
        assert length_one == length_two, "Invalid ROFS length!"
        assert file_count != 0, "Zero file partition detected!"

        # Begin parsing.
        for index in range(file_count):
            file_name, file_offset, file_length = struct.unpack_from("<4x32s4xII24x", data.read(72))
            # Determine filename based on null terminator.
            file_name = file_name.split(b'\x00')[0]
            file_name = file_name.decode('utf-8')

            contents = passed_data[file_offset:file_offset+file_length]
            file = ROFSFile(file_name, contents)
            self.files.append(file)


def find_rofs(contents: bytes) -> [ROFS, None]:
    """Attempts to find the ROFS contents in a file."""
    # TODO(spotlightishere): Properly determine ROFS location from header.
    location = 0
    while True:
        try:
            location = contents.index(b"ROFS", location)
        except ValueError:
            print("Unable to find ROFS partition!")
            return None

        try:
            return ROFS(contents[location:])
        except AssertionError:
            # Increment past this location in order to continue searching.
            location += 4
