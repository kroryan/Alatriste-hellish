# Captain Alatriste for Marta

A fan-made character skin for Marta in *Hellish Quart*. It runs on Marta's native 68-joint skeleton, with her original moves and rapier, and ships with the Marta first-person (FPP) compatibility adjustment.

- **Clean model.** A T-pose source without extra ornaments. It has PBR textures at 2048 and is reduced from 2M to 80k triangles. Each part stays under the 65k vertices the game's wound decal builder supports.
- **Joints from the geometry.** The source has no rig. [step2_landmarks.py](blender_work/step2_landmarks.py) places the joints itself:
  - shoulders, elbows and wrists come from vertical sections of the horizontal arms, and the wrist sits one hand length from the fingertips;
  - knees and ankles come from the leg sections;
  - the trunk follows Marta's proportions;
  - the fingers use Marta's hand layout, palm down.
- **Bone-heat weights, no shoulder triangles.** [heat_weights.py](blender_work/heat_weights.py) solves bone heat on a watertight voxel proxy at 10× scale, then copies the weights back to the real mesh. A vertex only follows bones it can "see" through the mesh, so the torso side and the armpit never follow the arm.
- **No stretched neck.** Alatriste's shoulders are 7 cm higher than Marta's, so the whole model is scaled to her shoulder height (×0.953) instead of stretching or squashing parts.
- **Rigid head and hair.**
- **No ghost body when hit.** Marta's 17 wound overlay meshes (`DecalBloody`, `DecalSpine1`, ...) are shaped like her own body. The visibility controller keeps them hidden under the skin, together with her stock face.

## Layout

- `model/Alatriste_Marta.blend`: the fitted result on Marta's skeleton, editable in Blender 5.3.
- `model/references/`: the four reference views.
- `model/selector_portrait.png`: the selector picture.
- `model/Alatriste_source.glb` is not in the repository because of its size (75 MB). Place it there to rebuild from scratch.
- `blender_work/`:
  - `step1_prepare.py` decimates and cleans the source and exports the textures (the glTF MR map is the shader's ORM);
  - `step2_landmarks.py` derives the joints;
  - `step3_rig_marta.py` scales the model, fits Marta's limbs and hands, computes the weights, carries the mesh into Marta's bind pose and splits off the rigid head;
  - `verify_skeleton.py` checks the 68 bones and the weights.
- `unity_project/`: Unity 2019.4.0f1 project (menu **Alatriste → Construir mod**).
- `release/README.txt`: the English text shipped in the zip. The zip contains only the four bundles and this README; releases never include scripts.
- [Optional manual FPP adjustment](FPP.md).

## Rebuild

Copy `Hellish Quart_Data/Managed/PlayMaker.dll` from your own installation to `unity_project/Assets/Plugins/`, then run:

```powershell
$blender="C:\Program Files\Blender Foundation\Blender 5.3\blender.exe"
$skel="unity_project\Assets\AlatristeMod\Editor\MartaSkeleton.json"
& $blender -b --factory-startup -P blender_work\step1_prepare.py -- model\Alatriste_source.glb model\Alatriste_source.glb build
& $blender -b --factory-startup -P blender_work\step2_landmarks.py -- build $skel
& $blender -b --factory-startup -P blender_work\step3_rig_marta.py -- build $skel
& $blender -b --factory-startup -P blender_work\verify_skeleton.py -- build\marta\Skin.fbx $skel
.\build.ps1
```

`build.ps1` is a developer build script and is never part of the release. It runs the Unity batch build and copies the four bundles into `release/`. It also creates `Alatriste_Marta.zip`.

## Install

Close the game and copy the four bundles from the zip into `Hellish Quart_Data/StreamingAssets/`. Then select Marta and choose the skin under **Custom Skin**. Delete the same four files to uninstall.

## First-person (FPP) adjustment

Optional and manual: `release/README.txt` lists the 4 bytes of Marta's skin loader (PlayMaker FSM, path ID 67815) in `resources.assets` to change with a hex editor. In the game version of November 2026 (resources.assets of 895,141,008 bytes) the true event of `isFPP?` goes from `yes` to `no`, so first person uses the selected custom skin.

Thanks to Kubold for *Hellish Quart* and its modding tools, and to Arturo Pérez-Reverte for the character who inspired the skin.
