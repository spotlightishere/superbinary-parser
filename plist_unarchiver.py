import plistlib
from typing import Union


class SomewhatKeyedUnarchiver(object):
    """A loose implementation of a NSKeyedUnarchiver.

    This is very loosely put together:
    Please do not consider this as a reference implementation!
    This project's primary focus is on SuperBinary parsing, not NSKeyedUnarchiver :)"""

    plist: dict

    def __init__(self, plist_data: bytes):
        self.plist = plistlib.loads(plist_data, fmt=plistlib.FMT_BINARY)

        # Sanity checks for our assumptions:
        assert self.plist["$archiver"] == "NSKeyedArchiver", "Unknown archive type!"
        assert self.plist["$version"] == 100000, "Unknown version!"

    def get_object(self, uid: plistlib.UID) -> any:
        """Returns a root object at the given index. This effectively resolves a UID."""
        return self.plist["$objects"][uid]

    def get_class_name(self, current_object: dict) -> str:
        """Returns the class name for the given object."""
        # This class's UID is present under the special "$class" key.
        # We can then look it up within the root "$objects" dictionary.
        class_uid = current_object["$class"]
        class_info = self.plist["$objects"][class_uid]

        # For our intents and purposes, we only need to care about
        # "$classname" within this class's info.
        return class_info["$classname"]

    def unarchive_root_object(self) -> dict:
        """Begins iterating through the root object, unarchiving accordingly."""

        # As a special case: here, we begin recursing via the special key "$top",
        # in which we assume that it only has one object.
        # This _should_ be UID 1, but you never know.

        root_class_uid = self.plist["$top"]["root"]
        root_object = self.get_object(root_class_uid)
        return self.unarchive_object(root_object)

    def unarchive_object(self, current_object: Union[dict, list]) -> any:
        """Unarchives an object."""
        object_class = self.get_class_name(current_object)

        # Ensure this is a class type we're familiar with.
        if object_class == "NSMutableDictionary" or object_class == "NSDictionary":
            return self.unarchive_dict(current_object)
        elif object_class == "NSMutableArray" or object_class == "NSArray":
            return self.unarchive_array(current_object)
        else:
            raise AssertionError(f'Unknown archived class type "{object_class}"!')

    def unarchive_dict(self, current_object: dict) -> dict:
        """Unarchives a NS(Mutable)Dictionary."""
        # For a dictionary, we have "NS.keys" and "NS.objects".
        keys = current_object["NS.keys"]
        values = current_object["NS.objects"]

        assert len(keys) == len(values), "Invalid dictionary length!"

        # Let's transform our results to {key UID => object UID}.
        uid_mapping = dict(zip(keys, values))

        # First, we'll resolve key names. They should all be strings.
        result = {}
        for key_uid, value_uid in uid_mapping.items():
            # Obtaining the key's name is as simple as looking up its UID.
            key_name = self.get_object(key_uid)
            resolved_object = self.get_object(value_uid)

            # If an object's value is a dictionary/array, we assume they
            # are another object, and we unarchive them accordingly.
            # Otherwise, preserve as-is.
            if isinstance(resolved_object, dict) or isinstance(resolved_object, list):
                value_contents = self.unarchive_object(resolved_object)
            else:
                value_contents = resolved_object

            result[key_name] = value_contents

        return result

    def unarchive_array(self, array: dict) -> list:
        """Resolves a NS(Mutable)Array."""
        result = []

        # NSArrays simply contain an array of "NS.objects".
        # We can iterate and resolve.
        array_objects = array["NS.objects"]
        for value_uid in array_objects:
            resolved_object = self.get_object(value_uid)

            # If an object's value is a dictionary/array, we assume they
            # are another object, and we unarchive them accordingly.
            # Otherwise, preserve as-is.
            if isinstance(resolved_object, dict) or isinstance(resolved_object, list):
                value_contents = self.unarchive_object(resolved_object)
            else:
                value_contents = resolved_object

            result.append(value_contents)
        return result
