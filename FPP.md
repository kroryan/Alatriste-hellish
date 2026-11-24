# Optional first-person compatibility

The manual skin installation works without changing game data. In the game version of **November 2026**, Marta's default first-person loader bypasses selected custom skins. This optional adjustment makes it use the normal custom-skin selection branch in first person. It applies to Marta's loader and can also affect other custom skins selected for Marta.

1. Close the game. In Steam, choose **Manage → Browse local files**.
2. Back up `Hellish Quart_Data/resources.assets` to a separate folder. The supported original file is exactly **895,141,008 bytes**. Use these offsets only for the game version listed above and only when the original bytes match all four rows.
3. Open `resources.assets` with a hex editor in **overwrite** mode. All offsets in the table are hexadecimal and measured from the start of the file.

| Offset | Original | Replacement |
| --- | --- | --- |
| `0x32B93AC0` | `03` | `02` |
| `0x32B93AC4` | `79` | `6E` |
| `0x32B93AC5` | `65` | `6F` |
| `0x32B93AC6` | `73` | `00` |

4. Save and confirm the file size is unchanged. To undo the adjustment, restore the backup on the same build or verify the game's files through Steam.

For review, the exact original and changed controller hashes and offset range are recorded in [the patch metadata](nexus_package/marta_fpp_patch.json). The object is the PlayMaker FSM at path ID 67815 (`CharacterMarfa/Mafra5 Puppet/Mafra5/SetSkin`). The change alters the true event of the `isFPP?` test from `yes` to `no`, matching the existing route for selected custom skins. It does not ship a replacement game asset. Steam updates or file verification may restore the original data.
