import bpy,os,math,json
from mathutils import Matrix,Vector
bpy.ops.wm.read_factory_settings(use_empty=True)
bpy.ops.import_scene.gltf(filepath=os.path.abspath('alatriste_img.glb'))
meshes=[o for o in bpy.data.objects if o.type=='MESH']
for m in meshes:
 m.data.transform(Matrix.Rotation(-math.pi/2,4,'Z') @ m.matrix_world);m.matrix_world=Matrix.Identity(4)
bpy.ops.object.select_all(action='DESELECT')
for m in meshes:m.select_set(True)
bpy.context.view_layer.objects.active=meshes[0];bpy.ops.object.join();m=meshes[0]
vs=[v.co for v in m.data.vertices];lo=min(v.z for v in vs);hi=max(v.z for v in vs);s=1.92/(hi-lo)
m.data.transform(Matrix.Scale(s,4) @ Matrix.Translation((0,0,-lo)))
# Center on torso rather than the asymmetric cape bounding box.
vs=[v.co for v in m.data.vertices if 1.58<v.co.z<1.68];cx=(min(v.x for v in vs)+max(v.x for v in vs))/2;cy=(min(v.y for v in vs)+max(v.y for v in vs))/2
m.data.transform(Matrix.Translation((-cx,-cy,0)))
tris=sum(len(p.vertices)-2 for p in m.data.polygons);d=m.modifiers.new('GameOptimization','DECIMATE');d.ratio=120000/tris;bpy.ops.object.modifier_apply(modifier=d.name)
print('MODEL',len(m.data.vertices),sum(len(p.vertices)-2 for p in m.data.polygons),flush=True)
for im in bpy.data.images:print('TEXTURE',im.name,tuple(im.size),flush=True)
sc=bpy.context.scene;sc.render.engine='BLENDER_WORKBENCH';sc.display.shading.color_type='TEXTURE';sc.display.shading.show_backface_culling=True;sc.render.resolution_x=900;sc.render.resolution_y=1100
c=bpy.data.cameras.new('cam');o=bpy.data.objects.new('cam',c);sc.collection.objects.link(o);sc.camera=o;c.type='ORTHO';c.ortho_scale=2.25
out=os.path.abspath('blender_work/img');os.makedirs(out,exist_ok=True)
for n,pos in [('raw_front',(0,-4,1)),('raw_back',(0,4,1)),('raw_side',(4,0,1))]:
 o.location=pos;o.rotation_euler=(Vector((0,0,1))-o.location).to_track_quat('-Z','Y').to_euler();sc.render.filepath=os.path.join(out,n+'.png');bpy.ops.render.render(write_still=True)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(out,'SourceAligned.blend'))
