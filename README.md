# superbinary-parser

Provides a few tools to manipulate a [SuperBinary](https://github.com/hack-different/apple-knowledge/blob/master/docs/UARP_and_FOTA.md#uarp---universal-accessory-restore-protocol).

This tool permits you to extract the various payload types within SuperBinaries.
Extracts a [FOTA](https://github.com/hack-different/apple-knowledge/blob/master/docs/UARP_and_FOTA.md#fota---firmware-over-the-air) (MediaTek OTA)
from within a [SuperBinary](https://github.com/hack-different/apple-knowledge/blob/master/docs/UARP_and_FOTA.md#uarp---universal-accessory-restore-protocol) container.

Note that this tool has only been tested on the firmware available for the [Beats Studio Buds](https://mesu.apple.com/assets/macos/com_apple_MobileAsset_UARP_A2513/com_apple_MobileAsset_UARP_A2513.xml)
and the [MagSafe Charger](https://mesu.apple.com/assets/com_apple_MobileAsset_UARP_A2140/com_apple_MobileAsset_UARP_A2140.xml).

## Installation
As this package depends on a secondary repository for custom LZMA decoding,
t's recommended to install this package within a virtual environment.

Assuming a UNIX operating system, execute similar to the following:
```
git clone https://github.com/spotlightishere/superbinary-parser
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

You can then `python3 main.py`:
```
> python3 main.py
usage: main.py [-h] [--extract-payloads | --no-extract-payloads] [--decompress-fota | --no-decompress-fota] [--extract-rofs EXTRACT_ROFS] source output_dir
main.py: error: the following arguments are required: source, output_dir
```