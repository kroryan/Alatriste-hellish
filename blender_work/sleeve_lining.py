"""Add closed undershirt sleeves beneath the generated jacket."""
from mathutils.bvhtree import BVHTree
from mathutils.geometry import barycentric_transform
body=next(part for part in parts if part.name=='AlatristeBody')
old=body.data

# Patch closed boundary loops in the armhole using their own skinned
# vertices. The cloth beneath it covers the larger irregular openings.
shell=bmesh.new()
shell.from_mesh(old)
boundaries={edge for edge in shell.edges if edge.is_boundary}
uv_layer=shell.loops.layers.uv.active
patched=0
while boundaries:
    first=boundaries.pop()
    boundary={first}
    pending=[first]
    while pending:
        edge=pending.pop()
        for v in edge.verts:
            connected=[other for other in v.link_edges if other in boundaries]
            for other in connected:
                boundaries.remove(other)
                boundary.add(other)
            pending.extend(connected)
    rim={v for edge in boundary for v in edge.verts}
    if len(boundary)!=len(rim) or not 4<=len(rim)<=145:continue
    if any(sum(edge in boundary for edge in v.link_edges)!=2 for v in rim):continue
    center=sum((v.co for v in rim),Vector())/len(rim)
    if not (.155<abs(center.x)<.43 and 1.25<center.z<1.49):continue
    # Large openings need the independently skinned gusset below. A fan
    # across such a rim becomes a sheet dragged between chest and biceps.
    if max((v.co-center).length for v in rim)>.047:continue
    seam_uv={v:next((loop[uv_layer].uv.copy() for loop in v.link_loops),None) for v in rim}
    patch=bmesh.ops.holes_fill(shell,edges=list(boundary),sides=145)['faces']
    # Select the nearest existing UV chart on each rim, never a random
    # vertex loop that may point to an unrelated part of the texture atlas.
    for face in patch:
        face.smooth=True
        face.material_index=0
        seed=next((seam_uv[v] for v in rim if seam_uv[v] is not None),None)
        if seed is not None:
            for loop in face.loops:
                candidates=[l[uv_layer].uv for l in loop.vert.link_loops if l.face not in patch]
                uv=min(candidates,key=lambda uv:(uv-seed).length_squared) if candidates else seed
                loop[uv_layer].uv=uv if (uv-seed).length<.045 else seed
    if patch:
        bmesh.ops.triangulate(shell,faces=patch)
        patched+=1
shell.to_mesh(old)
shell.free()
old.update()
print('ARMHOLE_SEAMS_CLOSED',patched,flush=True)

vertices=[]
faces=[]
uvs=[]
weights=[]
surface_uv={}
for loop,uv in zip(old.loops,old.uv_layers.active.data):
    surface_uv.setdefault(loop.vertex_index,tuple(uv.uv))

for side in ('Left','Right'):
    upper,lower,hand=side+'Arm',side+'ForeArm',side+'Hand'
    shoulder,elbow,wrist=[body.matrix_world.inverted() @ (MW @ original[n]).translation for n in (upper,lower,hand)]
    upper_axis=(elbow-shoulder).normalized()
    forearm_axis=(wrist-elbow).normalized()
    upper_length=(elbow-shoulder).length
    forearm_length=(wrist-elbow).length
    length=upper_length+forearm_length
    sleeve=[]
    for vertex in old.vertices:
        upper_along=(vertex.co-shoulder).dot(upper_axis)
        forearm_along=(vertex.co-elbow).dot(forearm_axis)
        if (vertex.co-elbow).dot(upper_axis+forearm_axis)>0:
            along=upper_length+forearm_along
        else:
            along=upper_along
        influence=sum(g.weight for g in vertex.groups if body.vertex_groups[g.group].name in (upper,lower))
        if influence>.65 and -.02<along<length+.02:
            sleeve.append((vertex,along))
    if len(sleeve)<100:
        raise RuntimeError('Cannot locate sleeve backing on '+side)
    sleeve_ids={vertex.index for vertex,_ in sleeve}
    sleeve_polys=[tuple(poly.vertices) for poly in old.polygons
                  if len(poly.vertices)==3 and sum(index in sleeve_ids for index in poly.vertices)>=2]
    outer_positions=[vertex.co.copy() for vertex in old.vertices]
    sleeve_surface=BVHTree.FromPolygons(outer_positions,sleeve_polys,all_triangles=True)
    cloth=min(sleeve,key=lambda item:abs(item[1]-.34*upper_length)+
              (item[0].co-(shoulder+upper_axis*(.34*upper_length)-Vector((0,0,.06)))).length)[0]
    cloth_uv=surface_uv[cloth.index]

    # A single closed undersleeve extends from inside the rib cage to the
    # cuff, including the inner elbow that the short axilla plug missed.
    rings=28
    segments=28
    start=len(vertices)
    for j in range(rings):
        t=j/(rings-1)
        along=-.113+(length+.104)*t
        elbow_mix=smooth(-.070,.070,along-upper_length)
        axis=upper_axis.lerp(forearm_axis,elbow_mix).normalized()
        radial=axis.cross(Vector((0,0,1))).normalized()
        vertical=radial.cross(axis).normalized()
        center=shoulder+upper_axis*min(along,upper_length)+forearm_axis*max(0.,along-upper_length)
        nearby=[v.co-center for v,a in sleeve if abs(a-along)<.027]
        if len(nearby)>24:
            center+=radial*np.clip(np.median([v.dot(radial) for v in nearby]),-.026,.026)*.65
            center+=vertical*np.clip(np.median([v.dot(vertical) for v in nearby]),-.026,.026)*.65
        taper=smooth(upper_length,length,along)
        width=.035-.016*taper
        depth=.033-.016*taper
        axilla=(1-smooth(.042,.138,abs(along)))
        center-=vertical*(.014*axilla)
        chest=1-smooth(-.055,.106,along)
        wrist_mix=smooth(length-.062,length+.014,along)*.72
        for k in range(segments):
            angle=2*math.pi*k/segments
            lower_half=max(0.,-math.sin(angle))
            radius=radial*((width+.011*axilla*lower_half)*math.cos(angle))+vertical*((depth+.021*axilla*lower_half)*math.sin(angle))
            # The inside seam has its own continuous gusset. Extend it
            # toward the ribs even if another scan fragment intercepts
            # the ray used to fit the rest of the liner.
            gusset=axilla*lower_half*(1-smooth(.052,.135,along))
            point,_,polygon,outer_radius=sleeve_surface.ray_cast(center,radius.normalized(),.15)
            weighted={upper:(1-chest)*(1-elbow_mix),lower:(1-chest)*elbow_mix*(1-wrist_mix),
                      hand:(1-chest)*elbow_mix*wrist_mix,'Spine1':chest}
            if polygon is not None:
                # Keep the liner under the surface and make built-in folds
                # share the outer sleeve's animation at the same angle.
                inset=radius.normalized()*min(radius.length,max(.005,outer_radius*.73))
                radius=inset.lerp(radius,.88*gusset)
                if len(sleeve_polys[polygon])==3 and along>.025:
                    indices=sleeve_polys[polygon]
                    a,b,c=[outer_positions[i] for i in indices]
                    barycentric=barycentric_transform(point,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
                    sampled={}
                    for i,influence in zip(indices,barycentric):
                        for group in old.vertices[i].groups:
                            name=body.vertex_groups[group.group].name
                            sampled[name]=sampled.get(name,0.)+max(0.,influence)*group.weight
                    weighted=mix(weighted,sampled,.82*smooth(.025,.105,along)*(1-gusset))
            p=center+radius
            vertices.append(tuple(p))
            uvs.append((cloth_uv[0]+.001*math.cos(angle),cloth_uv[1]+.002*t))
            # The gusset remains partly rooted in the chest under the upper
            # arm so the fabric covers the angle as the shoulder opens.
            follow=smooth(-.045,.117,along)
            weighted=mix(weighted,{'Spine1':1-follow,upper:follow},.90*gusset)
            strongest=sorted(weighted.items(),key=lambda item:item[1],reverse=True)[:4]
            total=sum(w for _,w in strongest)
            weights.append({name:w/total for name,w in strongest})
    for j in range(rings-1):
        for k in range(segments):
            a=start+j*segments+k
            b=start+j*segments+(k+1)%segments
            faces.append((a,a+segments,b+segments))
            faces.append((a,b+segments,b))
    for j,reverse in ((0,True),(rings-1,False)):
        ring=start+j*segments
        for k in range(1,segments-1):
            face=(ring,ring+k,ring+k+1)
            faces.append(face[::-1] if reverse else face)

# The upper sleeve moves away from the ribs during a high guard. A separate
# opaque torso layer covers the side of the jacket exposed by that motion.
torso_ids={v.index for v in old.vertices if 1.16<v.co.z<1.53 and abs(v.co.x)<.275
           and sum(g.weight for g in v.groups
                   if body.vertex_groups[g.group].name in ('Spine','Spine1','Neck'))>.64}
torso_faces=[poly for poly in old.polygons if len(poly.vertices)==3
             and sum(index in torso_ids for index in poly.vertices)>=2]
torso_polys=[tuple(poly.vertices) for poly in torso_faces]
torso_surface=BVHTree.FromPolygons(outer_positions,torso_polys,all_triangles=True)
atlas=old.uv_layers.active.data
torso_uvs=[tuple(atlas[i].uv.copy() for i in poly.loop_indices) for poly in torso_faces]
start=len(vertices)
torso_rings=24
torso_segments=48
for j in range(torso_rings):
    t=j/(torso_rings-1)
    z=1.198+.284*t
    center=Vector((.018,-.024,z))
    spine=smooth(1.205,1.36,z)
    for k in range(torso_segments):
        angle=2*math.pi*k/torso_segments
        direction=Vector((math.cos(angle),math.sin(angle),0))
        expected=1/math.sqrt((direction.x/.168)**2+(direction.y/.112)**2)
        hit,_,polygon,distance=torso_surface.ray_cast(center,direction,.28)
        radius=expected if hit is None else min(expected*1.05,max(.078,distance-.012))
        vertices.append(tuple(center+radius*direction))
        if polygon is None:
            hit,_,polygon,_=torso_surface.find_nearest(center+expected*direction)
        a,b,c=[outer_positions[i] for i in torso_polys[polygon]]
        u,v,w=[Vector((uv.x,uv.y,0)) for uv in torso_uvs[polygon]]
        projected=barycentric_transform(hit,a,b,c,u,v,w)
        uvs.append((projected.x,projected.y))
        weights.append({'Spine1':spine,'Spine':1-spine})
for j in range(torso_rings-1):
    for k in range(torso_segments):
        a=start+j*torso_segments+k
        b=start+j*torso_segments+(k+1)%torso_segments
        faces.extend(((a,b,b+torso_segments),(a,b+torso_segments,a+torso_segments)))
for j,reverse in ((0,True),(torso_rings-1,False)):
    ring=start+j*torso_segments
    for k in range(1,torso_segments-1):
        face=(ring,ring+k,ring+k+1)
        faces.append(face[::-1] if reverse else face)

lining_mesh=bpy.data.meshes.new('OpaqueSleeveLining')
lining_mesh.from_pydata(vertices,[],faces)
bm=bmesh.new()
bm.from_mesh(lining_mesh)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
if any(not edge.is_manifold for edge in bm.edges):
    raise RuntimeError('The undersleeve must be a closed surface')
bm.to_mesh(lining_mesh)
bm.free()
lining_mesh.materials.append(old.materials[0])
uv_layer=lining_mesh.uv_layers.new(name=old.uv_layers.active.name)
for loop in lining_mesh.loops:
    uv_layer.data[loop.index].uv=uvs[loop.vertex_index]
for poly in lining_mesh.polygons:poly.use_smooth=True
lining=bpy.data.objects.new('SleeveLining',lining_mesh)
bpy.context.scene.collection.objects.link(lining)
lining.matrix_world=body.matrix_world
for i,weighted in enumerate(weights):
    for name,weight in weighted.items():
        if weight<=.0001:continue
        group=lining.vertex_groups.get(name) or lining.vertex_groups.new(name=name)
        group.add([i],weight,'REPLACE')
bpy.ops.object.select_all(action='DESELECT')
body.select_set(True)
lining.select_set(True)
bpy.context.view_layer.objects.active=body
bpy.ops.object.join()
# Joining may append a material slot. Preserve a single decal-compatible section.
for poly in body.data.polygons:poly.material_index=0
while len(body.data.materials)>1:body.data.materials.pop(index=1)
print('SLEEVE_LINING',len(vertices),len(faces),flush=True)
