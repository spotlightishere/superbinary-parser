# superbinary-parser

Provides a few tools to manipulate a [SuperBinary](https://github.com/hack-different/apple-knowledge/blob/60ef78501b02b7c304ed6fe3c84d0c7f7e2a45eb/docs/UARP_and_FOTA.md#uarp---universal-accessory-restore-protocol).

This tool permits you to extract the various payload types within SuperBinaries.
Extracts a [FOTA](https://github.com/hack-different/apple-knowledge/blob/60ef78501b02b7c304ed6fe3c84d0c7f7e2a45eb/docs/UARP_and_FOTA.md#fota---firmware-over-the-air) (MediaTek OTA)
from within a [SuperBinary](https://github.com/hack-different/apple-knowledge/blob/60ef78501b02b7c304ed6fe3c84d0c7f7e2a45eb/docs/UARP_and_FOTA.md#uarp---universal-accessory-restore-protocol) container.

Note that this tool has only been tested on the firmware available for the [Beats Studio Buds](https://mesu.apple.com/assets/macos/com_apple_MobileAsset_UARP_A2513/com_apple_MobileAsset_UARP_A2513.xml)
and the [MagSafe Charger](https://mesu.apple.com/assets/com_apple_MobileAsset_UARP_A2140/com_apple_MobileAsset_UARP_A2140.xml).