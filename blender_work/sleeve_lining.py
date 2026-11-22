"""Add closed undershirt sleeves beneath the generated jacket."""
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
    if max((v.co-center).length for v in rim)>.085:continue
    seam_uv={v:next((loop[uv_layer].uv.copy() for loop in v.link_loops),None) for v in rim}
    patch=bmesh.ops.holes_fill(shell,edges=list(boundary),sides=145)['faces']
    for face in patch:
        face.smooth=True
        face.material_index=0
        for loop in face.loops:
            if seam_uv[loop.vert] is not None:loop[uv_layer].uv=seam_uv[loop.vert]
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
    upper,lower=side+'Arm',side+'ForeArm'
    shoulder,elbow=[body.matrix_world.inverted() @ (MW @ original[n]).translation for n in (upper,lower)]
    axis=(elbow-shoulder).normalized()
    length=(elbow-shoulder).length
    radial=axis.cross(Vector((0,0,1))).normalized()
    vertical=radial.cross(axis).normalized()
    sleeve=[]
    for vertex in old.vertices:
        along=(vertex.co-shoulder).dot(axis)
        influence=sum(g.weight for g in vertex.groups if body.vertex_groups[g.group].name in (upper,lower))
        if influence>.72 and -.02<along<length+.03:
            sleeve.append((vertex,along))
    if len(sleeve)<100:
        raise RuntimeError('Cannot locate sleeve backing on '+side)
    cloth=min(sleeve,key=lambda item:abs(item[1]-.34*length)+
              abs((item[0].co-shoulder).dot(radial))+
              abs((item[0].co-shoulder).dot(vertical)+.062))[0]
    cloth_uv=surface_uv[cloth.index]

    # Run the cloth from inside the jacket across the shoulder and down
    # the upper sleeve. The lower half bridges the open axilla.
    rings=13
    segments=24
    start=len(vertices)
    for j in range(rings):
        t=j/(rings-1)
        along=length*(-.35+.93*t)
        center=shoulder+axis*along
        nearby=[v.co-(shoulder+axis*a) for v,a in sleeve if abs(a-along)<.032]
        if len(nearby)>24:
            center+=radial*float(np.median([v.dot(radial) for v in nearby]))*.80
            center+=vertical*float(np.median([v.dot(vertical) for v in nearby]))*.80
        profile=(.58+.42*math.sin(math.pi*t))*(1-.21*t)
        center-=vertical*.010
        for k in range(segments):
            angle=2*math.pi*k/segments
            lower_half=max(0.,-math.sin(angle))
            p=center+profile*(radial*(.041*math.cos(angle))+vertical*((.032+.038*lower_half)*math.sin(angle)))
            vertices.append(tuple(p))
            uvs.append((cloth_uv[0]+.001*math.cos(angle),cloth_uv[1]+.002*t))
            chest=1-smooth(.08,.47,t)
            weights.append({upper:1-chest,'Spine1':chest})
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

lining_mesh=bpy.data.meshes.new('OpaqueSleeveLining')
lining_mesh.from_pydata(vertices,[],faces)
bm=bmesh.new()
bm.from_mesh(lining_mesh)
bmesh.ops.recalc_face_normals(bm,faces=list(bm.faces))
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
