import bpy,os,math,json,heapq,time
import numpy as np
from mathutils import Matrix,Vector
ROOT=os.path.abspath('.');OUT=os.path.join(ROOT,'blender_work/marta');os.makedirs(OUT,exist_ok=True);t0=time.time()
bpy.ops.wm.open_mainfile(filepath=os.path.join(ROOT,'blender_work/img/SourceAligned.blend'))
mesh=next(o for o in bpy.data.objects if o.type=='MESH');mesh.name='AlatristeBody'
# Keep the original continuous garment surface and weld only duplicated UV seams.
import bmesh
bm=bmesh.new();bm.from_mesh(mesh.data);bmesh.ops.remove_doubles(bm,verts=list(bm.verts),dist=.000008)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces));bm.to_mesh(mesh.data);bm.free();mesh.data.update()
for p in mesh.data.polygons:p.use_smooth=True
# Separate the rigid head without cutting or removing any triangles.
head_faces={p.index for p in mesh.data.polygons if p.center.z>1.615}
base=mesh.data.materials[0];headmat=base.copy();headmat.name='HeadMaterial';mesh.data.materials.append(headmat)
for poly in mesh.data.polygons:poly.material_index=1 if poly.index in head_faces else 0
cape_faces=set();capeverts=set();capeinterior=set()
# Actual Marta/Mafra5 skeleton extracted from this installation.
native=json.load(open(os.path.join(ROOT,'game_reference/MartaSkeleton.json')))
C=Matrix(((-1,0,0,0),(0,0,-1,0),(0,1,0,0),(0,0,0,1)))
ad=bpy.data.armatures.new('MartaSkeleton');ao=bpy.data.objects.new('Armature',ad);bpy.context.scene.collection.objects.link(ao);bpy.context.view_layer.objects.active=ao;ao.select_set(True);bpy.ops.object.mode_set(mode='EDIT')
for n in native['bones']:
 b=ad.edit_bones.new(n['name']);b.length=.05
 W=Matrix(n['world']);R=C @ W.to_3x3().to_4x4() @ C.inverted();R.translation=C.to_3x3() @ W.translation;b.matrix=R
 if n['parent']:b.parent=ad.edit_bones[n['parent']]
bpy.ops.object.mode_set(mode='OBJECT')

arm=next(o for o in bpy.data.objects if o.type=='ARMATURE');MW=arm.matrix_world.copy();IMW=MW.inverted();original={b.name:b.matrix_local.copy() for b in arm.data.bones};origlen={b.name:b.length for b in arm.data.bones}
bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
def head(n):return MW @ arm.data.edit_bones[n].head
def move(n,target):
 b=arm.data.edit_bones[n];delta=IMW.to_3x3() @ (Vector(target)-head(n))
 for q in [b]+list(b.children_recursive):q.translate(delta)
def turn(n,child,target):
 b=arm.data.edit_bones[n];h=head(n);d=head(child)-h;r=d.normalized().rotation_difference((Vector(target)-h).normalized()).to_matrix().to_4x4();t=IMW @ Matrix.Translation(h) @ r @ Matrix.Translation(-h) @ MW
 for q in [b]+list(b.children_recursive):q.matrix=t @ q.matrix
for side,sg in [('Left',1),('Right',-1)]:
 move(side+'Arm',(sg*.215,-.005,1.46));turn(side+'Arm',side+'ForeArm',(sg*.29,-.005,1.22));move(side+'ForeArm',(sg*.29,-.005,1.22))
 turn(side+'ForeArm',side+'Hand',(sg*.355,-.075,.98));move(side+'Hand',(sg*.355,-.075,.98));turn(side+'Hand',side+'HandMiddle1',(sg*.355,-.105,.85))
 turn(side+'UpLeg',side+'Leg',(sg*.15,.015,.55));turn(side+'Leg',side+'Foot',(sg*.17,.04,.14))
edited={b.name:b.matrix.copy() for b in arm.data.edit_bones};bpy.ops.object.mode_set(mode='OBJECT')
children={'Hips':'Spine','Spine':'Spine1','Spine1':'Neck','Neck':'Head','Head':None}
for s in ['Left','Right']:
 for a,b in [('Shoulder','Arm'),('Arm','ForeArm'),('ForeArm','Hand'),('Hand','HandMiddle1'),('UpLeg','Leg'),('Leg','Foot'),('Foot','ToeBase'),('ToeBase','ToeBase_END')]:children[s+a]=s+b
def bh(n):return (MW @ edited[n]).translation
segs={n:(bh(n),bh(c) if c else bh(n)+Vector((0,0,.24))) for n,c in children.items()}
segs['Hips']=(bh('Hips')-Vector((0,0,.16)),bh('Spine'))
for s in ['Left','Right']:
 a,b=segs[s+'Hand'];segs[s+'Hand']=(a,a+(b-a).normalized()*.17)
V=np.array([tuple(v.co) for v in mesh.data.vertices]);N=len(V);names=list(children);D=[]
for n in names:
 a,b=segs[n];a=np.array(a);ab=np.array(b)-a;t=np.clip(((V-a)@ab)/(ab@ab),0,1);D.append(np.linalg.norm(V-(a+t[:,None]*ab),axis=1))
D=np.array(D)
adj=[[] for i in range(N)]
for e in mesh.data.edges:
 i,j=e.vertices;d=float(np.linalg.norm(V[i]-V[j]));adj[i].append((j,d));adj[j].append((i,d))
# Hand-painted anatomical envelopes with continuous shoulder transitions.
# No automatic weights, no geometry deletion and no face/hat deformation.
groups={n:mesh.vertex_groups.new(name=n) for n in names};rigidhead=[]
def geodesic(seeds):
 gd=np.full(N,np.inf);heap=[]
 for i in seeds:gd[i]=0.;heap.append((0.,int(i)))
 heapq.heapify(heap)
 while heap:
  d,i=heapq.heappop(heap)
  if d!=gd[i]:continue
  for j,dd in adj[i]:
   nd=d+dd
   if nd<gd[j]:gd[j]=nd;heapq.heappush(heap,(nd,j))
 return gd
xv,yv,zv=V.T
colorim=next(im for im in bpy.data.images if im.name.startswith('Color_'));cw,ch=colorim.size;cp=np.empty(cw*ch*4,dtype=np.float32);colorim.pixels.foreach_get(cp);cp=cp.reshape(ch,cw,4)
vc=np.zeros((N,3),dtype=np.float32)
for loop,uv in zip(mesh.data.loops,mesh.data.uv_layers.active.data):vc[loop.vertex_index]=cp[int(uv.uv.y*ch)%ch,int(uv.uv.x*cw)%cw,:3]
del cp
handregions={}
for side,sg in [('Left',1),('Right',-1)]:
 candidate=(sg*xv>.275)&(yv<.035)&(zv>.745)&(zv<1.015)&(np.ones(N,dtype=bool))
 seeds=set(np.where(candidate&(vc[:,0]>.42)&(vc[:,1]>.26)&(zv<.96))[0]);todo=list(seeds);seen=set(seeds)
 while todo:
  i=todo.pop()
  for j,dd in adj[i]:
   if candidate[j] and j not in seen:seen.add(j);todo.append(j)
 handregions[side]=seen
 print('HAND_REGION',side,len(seen),flush=True)
hands=set.union(*handregions.values())
bodymask=(np.abs(xv)<.15)|(zv<.80)|(zv>1.55)
for i in hands:bodymask[i]=False
bodyseeds=np.where(bodymask)[0]
db=geodesic(bodyseeds);armfields={}
for side,sg in [('Left',1),('Right',-1)]:
 seeds=[]
 for z in np.arange(.85,1.49,.025):
  ids=np.where((abs(zv-z)<.018)&(sg*xv>.17))[0]
  if len(ids):
   mx=max(sg*xv[ids]);seeds.extend(ids[sg*xv[ids]>mx-.026])
 if side=='Right':
  seeds.extend(np.where((sg*xv>.235)&(zv>1.10)&(zv<1.29))[0])
  seeds.extend(np.where((sg*xv>.19)&(zv>=1.29)&(zv<1.43))[0])
 armfields[side]=geodesic(seeds)
def smooth(a,b,x):
 t=max(0.,min(1.,(x-a)/(b-a)));return t*t*(3-2*t)
def mix(a,b,t):
 q={n:w*(1-t) for n,w in a.items()}
 for n,w in b.items():q[n]=q.get(n,0)+w*t
 return q
for i,v in enumerate(mesh.data.vertices):
 x,y,z=v.co;ax=abs(x);side='Left' if x>=0 else 'Right'
 if i in hands:
  vals={side+'Hand':1.}
 elif z>1.585 or (z>1.55 and ax<.11 and y<-.055):
  vals={'Head':1.};rigidhead.append(i)
 else:
  # Torso chain, with the neck transition entirely below the face.
  vals=mix({'Hips':1.},{'Spine':1.},smooth(1.02,1.16,z))
  vals=mix(vals,{'Spine1':1.},smooth(1.22,1.39,z))
  vals=mix(vals,{'Neck':1.},smooth(1.49,1.56,z))
  vals=mix(vals,{'Head':1.},smooth(1.555,1.585,z))
  if z<1.02:
   leg=mix({side+'UpLeg':1.},{side+'Leg':1.},1-smooth(.49,.61,z))
   leg=mix(leg,{side+'Foot':1.},1-smooth(.10,.20,z))
   leg=mix(leg,{side+'ToeBase':1.},(1-smooth(.035,.085,z))*smooth(.01,.12,-y))
   vals=mix(vals,leg,1-smooth(.84,1.00,z))
  if .70<z<1.54:
   cutoff=float(np.interp(z,[.79,.92,1.04,1.18,1.30,1.44,1.54],[.28,.28,.26,.22,.19,.14,.21]))
   delta=db[i]-armfields[side][i]
   af=smooth(-.045,.045,float(delta)) if np.isfinite(delta) else smooth(cutoff-.025,cutoff+.025,ax)
   if z<.98 and i not in hands:af=0.
   inds=[names.index(side+s) for s in ['Arm','ForeArm','Hand']]
   distance=float(min(D[j,i] for j in inds))
   af*=1.0
   af*=smooth(.70,.74,z)*(1-smooth(1.50,1.55,z))
   av=mix({side+'ForeArm':1.},{side+'Arm':1.},smooth(1.17,1.29,z))
   av=mix(av,{side+'Hand':1.},1-smooth(.945,1.015,z))
   av=mix(av,{side+'Shoulder':1.},smooth(1.36,1.49,z)*(1-smooth(.21,.31,ax)))
   vals=mix(vals,av,af)
 vals={n:w for n,w in vals.items() if w>.0001}
 top=sorted(vals.items(),key=lambda x:-x[1])[:4];total=sum(w for n,w in top)
 for n,w in top:groups[n].add([i],w/total,'REPLACE')
mesh.parent=arm;mesh.matrix_parent_inverse=MW.inverted();mod=mesh.modifiers.new('Armature','ARMATURE');mod.object=arm
for pb in arm.pose.bones:pb.matrix=original[pb.name];bpy.context.view_layer.update()
dg=bpy.context.evaluated_depsgraph_get();eo=mesh.evaluated_get(dg);em=eo.to_mesh();coords=[v.co.copy() for v in em.vertices];eo.to_mesh_clear();mesh.modifiers.remove(mod)
for v,c in zip(mesh.data.vertices,coords):v.co=c
exec(compile(open(os.path.join(ROOT,'blender_work/marta_fit.py')).read(),'marta_fit.py','exec'),globals())
coords=[v.co.copy() for v in mesh.data.vertices]
bad=[]
for e in mesh.data.edges:
 i,j=e.vertices;d=(coords[i]-coords[j]).length
 if d>.12 and np.linalg.norm(V[i]-V[j])<.035:bad.append((d,i,j))
for d,i,j in sorted(bad,reverse=True)[:20]:
 print('BAD_BIND',round(d,3),tuple(np.round(V[i],3)),[(mesh.vertex_groups[g.group].name,round(g.weight,2)) for g in mesh.data.vertices[i].groups],tuple(np.round(V[j],3)),[(mesh.vertex_groups[g.group].name,round(g.weight,2)) for g in mesh.data.vertices[j].groups],flush=True)
bpy.context.view_layer.objects.active=arm;bpy.ops.object.mode_set(mode='EDIT')
for b in arm.data.edit_bones:b.matrix=original[b.name];b.length=origlen[b.name]
bpy.ops.object.mode_set(mode='OBJECT')
for pb in arm.pose.bones:pb.matrix_basis=Matrix.Identity(4)
mod=mesh.modifiers.new('Armature','ARMATURE');mod.object=arm
# Split by material without deleting a single source face.
bpy.ops.object.select_all(action='DESELECT');mesh.select_set(True);bpy.context.view_layer.objects.active=mesh;bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.mesh.separate(type='MATERIAL');bpy.ops.object.mode_set(mode='OBJECT')
parts=[o for o in bpy.data.objects if o.type=='MESH']
for o in parts:
 used={p.material_index for p in o.data.polygons};mats=[o.data.materials[i].name for i in used]
 o.name='AlatristeCape' if any('CapeMaterial' in n for n in mats) else 'AlatristeHead' if any('HeadMaterial' in n for n in mats) else 'AlatristeBody'
exec(compile(open(os.path.join(ROOT,'blender_work/sleeve_lining.py')).read(),'sleeve_lining.py','exec'),globals())
sc=bpy.context.scene;sc.display.shading.background_type='VIEWPORT';sc.display.shading.background_color=(.17,.17,.17);sc.display.shading.show_backface_culling=True;sc.display.shading.show_cavity=False;sc.render.resolution_x=1000;sc.render.resolution_y=1200;sc.camera.data.ortho_scale=2.5
def render(n,pos):
 c=sc.camera;c.location=pos;c.rotation_euler=(Vector((0,0,1))-c.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(OUT,n+'.png');bpy.ops.render.render(write_still=True)
render('rest_front',(0,-4,1));render('rest_back',(0,4,1));render('rest_side',(4,0,1))
def point(n,child,d):
 bpy.context.view_layer.update();pb=arm.pose.bones[n];m=MW @ pb.matrix;h=m.translation;v=(MW @ arm.pose.bones[child].matrix).translation-h;r=v.normalized().rotation_difference(Vector(d).normalized()).to_matrix().to_4x4();pb.matrix=IMW @ Matrix.Translation(h) @ r @ Matrix.Translation(-h) @ m;bpy.context.view_layer.update()
for s,sg in [('Left',1),('Right',-1)]:point(s+'Arm',s+'ForeArm',(sg*.7,0,.7));point(s+'ForeArm',s+'Hand',(sg*.5,-.3,.7))
render('test_arms_up',(0,-4,1));render('test_arms_back',(0,4,1))
for pb in arm.pose.bones:pb.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update();point('RightArm','RightForeArm',(-.25,-.7,-.25));point('RightForeArm','RightHand',(.15,-.8,.15));point('LeftArm','LeftForeArm',(.4,.2,-.4))
render('test_guard',(2,-4,1.1))
for pb in arm.pose.bones:pb.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update();arm.pose.bones['Head'].rotation_mode='XYZ';arm.pose.bones['Head'].rotation_euler=(math.radians(25),math.radians(35),math.radians(-15));bpy.context.view_layer.update();render('test_head',(1,-3,1.1))
for pb in arm.pose.bones:pb.matrix_basis=Matrix.Identity(4)
bpy.context.view_layer.update()
texdir=os.path.join(OUT,'textures');os.makedirs(texdir,exist_ok=True)
for im in bpy.data.images:
 if im.type=='IMAGE':
  im.filepath_raw=os.path.join(texdir,im.name+'.png');im.file_format='PNG';im.save()
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT,'Alatriste_Marta.blend'))
bpy.ops.object.select_all(action='DESELECT');arm.select_set(True)
for o in parts:o.select_set(True)
bpy.ops.export_scene.fbx(filepath=os.path.join(OUT,'Skin.fbx'),use_selection=True,object_types={'ARMATURE','MESH'},add_leaf_bones=False,bake_anim=False,path_mode='COPY',embed_textures=True,use_mesh_modifiers=False,apply_scale_options='FBX_SCALE_NONE')
report={'triangles':sum(sum(len(p.vertices)-2 for p in o.data.polygons) for o in parts),'bones':len(arm.data.bones),'parts':{o.name:len(o.data.polygons) for o in parts},'rigid_head_vertices':len(rigidhead),'no_faces_removed':True,'seconds':time.time()-t0}
open(os.path.join(OUT,'rig_report.json'),'w').write(json.dumps(report,indent=2));print('MARTA_RIG_OK',report,flush=True)
