# superbinary-parser

Provides a few tools to manipulate a [SuperBinary](https://github.com/hack-different/apple-knowledge/blob/main/_docs/UARP_and_FOTA.md#uarp---universal-accessory-restore-protocol).

This tool permits you to extract the various UARP (Universal Accessory Restore Protocol) payload types within SuperBinaries.
SuperBinaries are used in various Apple accessories, including the AirPods Pro (2nd generation), Beats devices with a MediaTek chip and MagSafe accessories.
On Beats devices with a MediaTek chip, it can also extract the [FOTA](https://github.com/hack-different/apple-knowledge/blob/main/_docs/UARP_and_FOTA.md#fota---firmware-over-the-air) (MediaTek OTA)
in a SuperBinary container.

> **Note**
> This tool aims to maintain compatability with the latest version of SuperBinary available.
>
> For example, with AirPods Pro (2nd generation), the version of SuperBinary increased from 2 to 3
> in version 6.0. If parsing fails with a version 3 SuperBinary in the future, please file an issue!

## Installation
As this package depends on a secondary repository ([LZMAAlone](https://github.com/spotlightishere/LZMAAlone)) for custom LZMA decoding,
it's recommended to install this package within a virtual environment.

You'll need appropriate build tools for your system.
If you are installing on a Windows system, first download [Microsoft Visual C++ 14.0](https://visualstudio.microsoft.com/visual-cpp-build-tools/) or greater.

Assuming a UNIX operating system, execute similar to the following:
```
git clone https://github.com/spotlightishere/superbinary-parser
python3 -m venv venv
source venv/bin/activate
pip3 install -r requirements.txt
```

## Usage
You can then `python3 main.py`:
```
> python3 main.py
usage: main.py [-h] [--extract-payloads | --no-extract-payloads] [--decompress-fota | --no-decompress-fota] [--extract-rofs | --no-extract-rofs] [--decompress-payload-contents | --no-decompress-payload-contents] source output_dir
main.py: error: the following arguments are required: source, output_dir
```

If you are parsing a device that does not have an FOTA, you can split the SuperBinary and its plist using this syntax:
``` 
> python3 main.py --extract-payloads source output_dir
```

On Beats devices with a MediaTek chip and an FOTA container (like the Beats Studio Buds), it is also possible to extract the firmware sounds from the Read Only File System (ROFS) using this syntax:
``` 
> python3 main.py --extract-payloads --decompress-fota --extract-rofs FirmwareUpdate.uarp output_dir
```

The script will then extract all assets, such as sounds, to the output direction.
