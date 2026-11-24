# Step 2 (sources without a usable rig): derive the joints of a T-pose model
# from its geometry and write build/source_joints.json for step3.
#   blender -b -P step2_landmarks.py -- <build_dir> <MartaSkeleton.json>
# Mesh: facing -Y, +X is the character's left, arms horizontal.
import bpy, os, sys, json
import numpy as np
from mathutils import Matrix, Vector

BUILD, SKEL = sys.argv[sys.argv.index('--') + 1:][:2]
bpy.ops.wm.open_mainfile(filepath=os.path.join(BUILD, 'prepared.blend'))
mesh = next(o for o in bpy.data.objects if o.type == 'MESH')
V = np.array([tuple(v.co) for v in mesh.data.vertices]); X, Y, Z = V.T

native = {b['name']: b for b in json.load(open(SKEL))['bones']}
C = Matrix(((-1, 0, 0, 0), (0, 0, -1, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
NW = {n: C.to_3x3() @ Matrix(b['world']).translation for n, b in native.items()}
NS = (NW['LeftArm'].z + NW['RightArm'].z) / 2

# --- Arms: vertical cross-sections along X -----------------------------------
arms = {}
for side, s in (('Left', 1), ('Right', -1)):
    reach = (s * X).max()
    rows = []
    for x in np.arange(.12, reach, .01):
        ids = np.where((np.abs(s * X - x) < .006) & (Z > .95))[0]
        if len(ids) < 4: continue
        rows.append((x, Y[ids].mean(), (Z[ids].min() + Z[ids].max()) / 2, Z[ids].max() - Z[ids].min()))
    rows = np.array(rows)
    # The free arm starts where the vertical section becomes arm-sized.
    free = rows[rows[:, 3] < .20]
    x_a = free[0, 0]
    axis = lambda x: rows[np.argmin(np.abs(rows[:, 0] - x)), 1:3]
    tip_x = reach
    zs = axis(x_a + .05)[1]                                   # shoulder height
    hand_len = .19 * zs / 1.437
    x_sh = float(np.clip(x_a - .06, .15, .22))
    x_wr = tip_x - hand_len
    x_el = x_sh + (x_wr - x_sh) * .53
    p = lambda x, ref=None: np.array([s * x, *axis(x if ref is None else ref)])
    arms[side] = dict(shoulder=p(x_sh, x_a + .03), elbow=p(x_el), wrist=p(x_wr), tip=p(tip_x - .01))
    print('ARM', side, 'free_from', round(x_a, 3), 'shoulder', np.round(arms[side]['shoulder'], 3),
          'elbow', np.round(arms[side]['elbow'], 3), 'wrist', np.round(arms[side]['wrist'], 3),
          'tip', np.round(arms[side]['tip'], 3), flush=True)

S = (arms['Left']['shoulder'][2] + arms['Right']['shoulder'][2]) / 2
ratio = lambda n: NW[n].z / NS * S

def centre(z, half=.012, width=.2):
    ids = np.where((np.abs(Z - z) < half) & (np.abs(X) < width))[0]
    return np.array([(X[ids].min() + X[ids].max()) / 2, (Y[ids].min() + Y[ids].max()) / 2, z])

J = {}
def put(n, head, tail=None):
    J[n] = {'head': [float(v) for v in head], 'tail': [float(v) for v in (tail if tail is not None else head)], 'parent': None}

for n in ('Spine', 'Neck', 'Head'):
    put(n, centre(ratio(n)))
put('Spine2', centre(ratio('Spine1')))
put('Spine1', (np.array(J['Spine']['head']) + np.array(J['Spine2']['head'])) / 2)

def frame(d, l):
    d = d.normalized(); l = (l - d * l.dot(d)).normalized(); return Matrix((d, l, d.cross(l))).transposed()

for side, s in (('Left', 1), ('Right', -1)):
    a = arms[side]
    put(side + 'Shoulder', np.array([s * .03, a['shoulder'][1], ratio(side + 'Shoulder')]))
    put(side + 'Arm', a['shoulder']); put(side + 'ForeArm', a['elbow']); put(side + 'Hand', a['wrist'])
    # Fingers from Marta's hand layout, mapped onto this hand: pointing along
    # the arm, palm down, thumb forward (-Y), scaled to the hand length.
    hn = side + 'Hand'
    mh = NW[hn]; md = NW[hn + 'Middle1'] - mh; ml = NW[hn + 'Index1'] - NW[hn + 'Pinky1']
    td = Vector(a['tip'] - a['wrist']); R = frame(td, Vector((0, -1, 0))) @ frame(md, ml).transposed()
    k = td.length / (NW[hn + 'Middle4'] - mh).length
    tf = lambda q: np.array(Vector(a['wrist']) + R @ ((q - mh) * k))
    for f in ('Thumb', 'Index', 'Middle', 'Ring', 'Pinky'):
        for i in (1, 2, 3):
            put(f'{hn}{f}{i}', tf(NW[f'{hn}{f}{i}']), tf(NW[f'{hn}{f}{i + 1}']))
    # Legs: centre of this side's leg at Marta-proportional heights.
    def leg(z):
        ids = np.where((np.abs(Z - z) < .012) & (s * X > .0) & (np.abs(X) < .3))[0]
        return np.array([X[ids].mean(), Y[ids].mean(), z]) if len(ids) else np.array([s * .1, 0, z])
    hip = leg(ratio(side + 'UpLeg') - .12); hip[2] = ratio(side + 'UpLeg')
    put(side + 'UpLeg', hip); put(side + 'Leg', leg(ratio(side + 'Leg')))
    ank = leg(ratio(side + 'Foot')); put(side + 'Foot', ank)
    foot = np.where((Z < .06) & (s * X > 0))[0]
    toe = V[foot[np.argmin(Y[foot])]].copy(); toe[2] = .02
    tb = ank + (toe - ank) * .62; tb[2] = .03
    put(side + 'ToeBase', tb, toe)
put('Hips', (np.array(J['LeftUpLeg']['head']) + np.array(J['RightUpLeg']['head'])) / 2)
json.dump(J, open(os.path.join(BUILD, 'source_joints.json'), 'w'), indent=1)
print('LANDMARKS_OK shoulder_height', round(S, 3), 'neck', np.round(J['Neck']['head'], 3), 'head', np.round(J['Head']['head'], 3), flush=True)

# QA render: joints over the semi-transparent mesh.
for n, j in J.items():
    if any(f in n for f in ('Index', 'Ring', 'Pinky', 'Middle')): continue
    bpy.ops.mesh.primitive_uv_sphere_add(radius=.015, location=j['head'])
sc = bpy.context.scene; sc.render.engine = 'BLENDER_WORKBENCH'; sc.display.shading.light = 'FLAT'
sc.display.shading.color_type = 'OBJECT'; sc.display.shading.show_xray = True; sc.display.shading.xray_alpha = .35
sc.render.resolution_x = 1400; sc.render.resolution_y = 1000
cam = bpy.data.objects.new('c', bpy.data.cameras.new('c')); sc.collection.objects.link(cam); sc.camera = cam
cam.data.type = 'ORTHO'
for n, pos, size in (('landmarks_front', (0, -4, 1), 2.0), ('landmarks_side', (4, 0, 1), 2.0), ('landmarks_hand', (.62, -3, 1.42), .45)):
    cam.data.ortho_scale = size; cam.location = pos
    cam.rotation_euler = Vector((0, 1, 0)).to_track_quat('-Z', 'Y').to_euler() if pos[1] < 0 else (Vector((-1, 0, 0))).to_track_quat('-Z', 'Y').to_euler()
    sc.render.filepath = os.path.join(BUILD, n + '.png'); bpy.ops.render.render(write_still=True)
