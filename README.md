# Captain Alatriste for Marta

A fan-made character skin for Marta in *Hellish Quart*. It uses Marta's original moves and rapier. The source includes the Alatriste model, its textures, and the Unity build code.

## For reviewers

- [Unity build and rig integration](unity_project/Assets/AlatristeMod/Editor/AlatristeFinalBuild.cs) builds the skin and selector portrait from the editable assets.
- [Camera shader](unity_project/Assets/AlatristeMod/AlatristeDetailed.shader) clears geometry around the first-person camera while keeping the complete model visible in external shots.
- [Visibility controller](unity_project/Assets/AlatristeMod/Editor/AlatristeFppBuilder.cs) handles the original Marta face meshes that the game can reactivate during a camera change.
- [Optional manual FPP adjustment](FPP.md) documents the four-byte change to Marta's native skin-loading controller, the exact compatible build, and the verification data.

The editable Blender rig and the input GLB are in [model/](model/). The Unity project includes the mod's FBX, materials, textures, prefabs, preview scene and bone mapping. It does not distribute the game assemblies, original game meshes, the modding kit, or the compiled Nexus release.

## Build on Windows

1. Install Unity **2019.4.0f1** with Windows Standalone build support.
2. From your own Hellish Quart installation, copy `Hellish Quart_Data/Managed/PlayMaker.dll` to `unity_project/Assets/Plugins/PlayMaker.dll`. Keep the checked-in `.meta` file so the prefab finds that dependency. If Unity prompts to update the assembly for this editor version, accept the update.
3. Add `unity_project` to Unity Hub and open it. Use **Alatriste → Construir mod** to build the Windows bundles. The build writes the two bundles and their manifests to `mod_alatriste/` at the repository root.
4. To prepare the release ZIP, include `skin_marta_alatriste`, `pic_marta_alatriste`, and their two `.manifest` files. The extra Unity bundle index and its manifest are build outputs only.

## Install the skin manually

Close the game. In Steam, choose **Manage → Browse local files** for *Hellish Quart*. Copy the four release files directly into `Hellish Quart_Data/StreamingAssets/`. Start the game, select Marta, and choose Alatriste under **Custom Skin**. Remove the same four files to uninstall.

Use **Alatriste → Abrir escena** to open the Unity preview. The original in-game rapier mesh used in local pose previews is optional and excluded from this repository. Blender 5.3 can open `model/Alatriste_Marta.blend` for mesh and rig edits.

Thanks to Kubold for *Hellish Quart* and its modding tools, and to Arturo Pérez-Reverte for the character who inspired the skin.
