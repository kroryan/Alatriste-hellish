from mathutils import Quaternion
from mathutils.bvhtree import BVHTree
from mathutils.kdtree import KDTree
from mathutils.geometry import barycentric_transform
def load_reference(name):
 d=json.load(open(os.path.join(ROOT,'game_reference',name+'.json')))
 vs=[C.to_3x3() @ Vector(v) for v in d['vertices']];fs=[tuple(reversed(f)) for f in d['triangles']]
 return d,vs,fs,BVHTree.FromPolygons(vs,fs,all_triangles=True)
def field(d,vs,fs,bvh,p):
 q,normal,fi,distance=bvh.find_nearest(p)
 if fi is None:return {},p,100
 ia,ib,ic=fs[fi];a,b,c=vs[ia],vs[ib],vs[ic]
 uvw=barycentric_transform(q,a,b,c,Vector((1,0,0)),Vector((0,1,0)),Vector((0,0,1)))
 uvw=[max(0,float(x)) for x in uvw];tot=sum(uvw);uvw=[x/tot for x in uvw]
 vals={}
 for i,w in zip([ia,ib,ic],uvw):
  for bi,bw in zip(d['bone_indices'][i],d['bone_weights'][i]):
   n=d['bone_names'][bi];vals[n]=vals.get(n,0)+w*bw
 return vals,q,distance
def setweights(i,vals):
 i=int(i)
 top=[(n,w) for n,w in sorted(vals.items(),key=lambda p:-p[1]) if w>.0001][:4];tot=sum(w for n,w in top)
 if not tot:return
 for g in mesh.vertex_groups:g.remove([i])
 for n,w in top:
  g=mesh.vertex_groups.get(n) or mesh.vertex_groups.new(name=n);g.add([i],w/tot,'REPLACE')
def icp_fit(P,Q,wrist,axis):
 # Registration determines palm roll and size from Marta's actual hand surface.
 kd=KDTree(len(Q))
 for j,q in enumerate(Q):kd.insert(Vector(q),j)
 kd.balance();best=None
 for angle in [-90,-45,0,45,90,180]:
  R=Matrix.Rotation(math.radians(angle),3,axis);rr=np.array(R);tt=np.mean(Q,axis=0)-rr@np.mean(P,axis=0);scale=1.
  X=(P@rr.T)*scale+tt
  for step in range(18):
   target=np.array([tuple(kd.find(Vector(p))[0]) for p in X]);A=X.mean(axis=0);B=target.mean(axis=0);u,sv,vh=np.linalg.svd((X-A).T@(target-B));rot=vh.T@u.T
   if np.linalg.det(rot)<0:vh[-1]*=-1;rot=vh.T@u.T
   shift=B-rot@A;X=X@rot.T+shift;rr=rot@rr;tt=rot@tt+shift
  distances=np.array([kd.find(Vector(p))[2] for p in X]);score=float(np.mean(np.sort(distances)[:int(len(distances)*.9)]**2))
  if best is None or score<best[0]:best=(score,rr,tt,angle)
 return best
fit_report={}
for side,refname in [('Left','HandLMesh'),('Right','HandRMESH')]:
 d,rv,rf,bvh=load_reference(refname);h=(MW @ original[side+'Hand']).translation;kn=(MW @ original[side+'HandMiddle1']).translation;u=(kn-h).normalized()
 ids=sorted(handregions[side]);skin=[i for i in ids if (mesh.data.vertices[i].co-h).dot(u)>.02]
 target=np.array([tuple(v) for v in rv if (v-h).dot(u)>.02]);P=np.array([tuple(mesh.data.vertices[i].co) for i in skin[::3]])
 score,R,t,angle=icp_fit(P,target,h,u);print('PALM_FIT',side,'rms',math.sqrt(score),'roll',angle,flush=True)
 # Spread the palm-roll correction over the forearm, instead of concentrating
 # the whole rotation into the few centimetres occupied by the cuff.
 elbow=(MW @ original[side+'ForeArm']).translation;foreaxis=(h-elbow).normalized();forelength=(h-elbow).length
 palm_rotation=Matrix(R.tolist()).to_quaternion()
 spin=Vector(palm_rotation[1:]).dot(foreaxis)
 twist=Quaternion((palm_rotation.w,*(foreaxis*spin))).normalized()
 if twist.w<0:twist.negate()
 shift=Vector(R@np.array(h)+t)-h
 cuff_reference=load_reference('MankietLMESH' if side=='Left' else 'MankietRMESH')
 cloth_ids=[]
 for v in mesh.data.vertices:
  old={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
  influence=old.get(side+'ForeArm',0)+old.get(side+'Hand',0)
  if influence<.35 or v.index in ids:continue
  along=(v.co-elbow).dot(foreaxis)/forelength;strength=smooth(.12,1.0,along)*smooth(.35,.9,influence)
  if strength<=0:continue
  q=Quaternion().slerp(twist,strength)
  center=elbow+foreaxis*(v.co-elbow).dot(foreaxis)
  v.co=center+q@(v.co-center)+shift*strength
  if along>.73:cloth_ids.append(v.index)
 for i in ids:
  v=mesh.data.vertices[i];p=v.co.copy();length=(p-h).dot(u);fitted=Vector(R@np.array(p)+t);p=fitted
  vals,q,dist=field(d,rv,rf,bvh,p)
  # Conform fingers gently to the correctly proportioned neutral hand, retaining
  # the generated mesh and its original UVs and textures.
  iscloth=V[int(i),2]>.975 or (vc[int(i)].max()-vc[int(i)].min()<.075 and vc[int(i)].mean()>.40)
  conform=0. if iscloth else smooth(.035,.09,length)*.45
  if dist<.05:p=p.lerp(q,conform)
  v.co=p
  if iscloth:
   cloth_ids.append(int(i));vals,_,_=field(*cuff_reference,p)
  if vals:
   old={mesh.vertex_groups[g.group].name:g.weight for g in v.groups};tweight=1. if iscloth else smooth(.002,.025,length);combined={n:w*(1-tweight) for n,w in old.items()}
   for n,w in vals.items():combined[n]=combined.get(n,0)+w*tweight
   setweights(i,combined)
 # Keep the fabric cuff outside the wrist, with a bounded rounded silhouette.
 for i in cloth_ids:
  v=mesh.data.vertices[i];axispoint=elbow+foreaxis*(v.co-elbow).dot(foreaxis);rad=v.co-axispoint;r=rad.length
  if r>.052:v.co=axispoint+rad.normalized()*(.052+(r-.052)*.18)
  vals,_,_=field(*cuff_reference,v.co)
  if vals:setweights(i,vals)
 fit_report[side]={'registration_rms_m':math.sqrt(score),'palm_roll_initial_deg':angle,'hand_vertices':len(ids),'cuff_vertices_repaired':len(cloth_ids)}
# Use Marta's authored sleeve and wrist weights where reference surfaces overlap.
rd,rv,rf,bvh=load_reference('UpDress');changed=0
for v in mesh.data.vertices:
 if v.index in hands:continue
 old={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
 armweight=sum(w for n,w in old.items() if any(n.endswith(s) for s in ['Arm','ForeArm','Shoulder','Hand']))
 if armweight<.15:continue
 vals,q,dist=field(rd,rv,rf,bvh,v.co)
 if dist>.12 or not vals:continue
 if not any(('Arm' in n or 'Shoulder' in n or 'Hand' in n) and w>.10 for n,w in vals.items()):continue
 blend=.85*(1-smooth(.07,.12,dist));combined={n:w*(1-blend) for n,w in old.items()}
 for n,w in vals.items():combined[n]=combined.get(n,0)+w*blend
 setweights(v.index,combined);changed+=1
 # Stabilize the bend where the generated sleeve and Marta's reference sleeve
 # differ in shape. All sides of the sleeve share a continuous elbow profile.
for side in ('Left','Right'):
 upper=side+'Arm';lower=side+'ForeArm'
 shoulder,elbow,wrist=[(MW @ original[side+n]).translation for n in ('Arm','ForeArm','Hand')]
 axis=((elbow-shoulder).normalized()+(wrist-elbow).normalized()).normalized()
 for v in mesh.data.vertices:
  if v.index in hands:continue
  offset=(v.co-elbow).dot(axis)
  if abs(offset)>.145:continue
  vals={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
  arm_total=vals.get(upper,0)+vals.get(lower,0)
  if arm_total<.70:continue
  influence=smooth(.70,.94,arm_total)*(1-smooth(.085,.145,abs(offset)))
  fore=arm_total*smooth(-.077,.077,offset)
  vals[lower]=vals.get(lower,0)*(1-influence)+fore*influence
  vals[upper]=arm_total-vals[lower]
  setweights(v.index,vals)
# Both renderers must move the same vertices at the head/body boundary.
# Blend only the actual neck into the head; the shirt collar stays on the torso.
seam=set()
other=set()
for poly in mesh.data.polygons:
 (seam if poly.material_index==1 else other).update(poly.vertices)
seam &= other
for v in mesh.data.vertices:
 i=v.index
 if i in seam:
  setweights(i,{'Head':1.})
  continue
 if i not in other or V[i,2]<1.445:continue
 old={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
 x,y,z=V[i]
 arm_influence=sum(w for n,w in old.items() if 'Arm' in n or 'Hand' in n or 'Shoulder' in n)
 neck=smooth(1.505,1.575,z)*(1-smooth(.085,.155,abs(x)))
 heading=smooth(1.548,1.595,z)
 neck_weights={'Spine1':(1-neck)*(1-heading),'Neck':neck*(1-heading),'Head':heading}
 setweights(i,mix(old,neck_weights,max(smooth(1.485,1.565,z),1-smooth(.16,.42,arm_influence))))
# Smooth adjacent cloth weights across the shoulders and collar while locking
# the head seam, forearms and fitted fingers. This avoids isolated vertices
# pulling fabric across the joint as the torso and arms rotate.
bone_names=[group.name for group in mesh.vertex_groups]
weights=np.zeros((len(mesh.data.vertices),len(bone_names)),dtype=np.float32)
region=[]
for v in mesh.data.vertices:
 for group in v.groups:weights[v.index,group.group]=group.weight
 x,_,z=V[v.index]
 if v.index in other and v.index not in seam and 1.30<z<1.50 and abs(x)<.33:
  neighbors=[j for j,d in adj[v.index] if .00001<d<.027]
  if len(neighbors)>1:region.append((v.index,neighbors))
for _ in range(4):
 previous=weights.copy()
 for i,neighbors in region:
  weights[i]=.55*previous[i]+.45*previous[neighbors].mean(axis=0)
for i,_ in region:
 setweights(i,{bone_names[j]:weights[i,j] for j in np.argsort(weights[i])[-4:]})

# Rebuild each sleeve's weights from its own arm chain. The sampled garment
# field identifies the shoulder transition, but cannot pull distant pieces of
# the sleeve with the torso or send the cuff to an unrelated finger.
for side,sign in (('Left',1),('Right',-1)):
 upper,lower,hand,clavicle=[side+n for n in ('Arm','ForeArm','Hand','Shoulder')]
 shoulder,elbow,wrist=[(MW @ original[n]).translation for n in (upper,lower,hand)]
 upper_axis=(elbow-shoulder).normalized()
 lower_axis=(wrist-elbow).normalized()
 bend_axis=(upper_axis+lower_axis).normalized()
 for v in mesh.data.vertices:
  i=v.index
  if i in hands or i in seam or i not in other or sign*V[i,0]<.145:continue
  old={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
  arm_sum=sum(old.get(n,0) for n in (upper,lower,hand,clavicle))
  along=(v.co-shoulder).dot(upper_axis)
  longitudinal=(v.co-elbow).dot(bend_axis)
  radial_distance=((v.co-shoulder)-upper_axis*along).length
  upper_clamped=max(0.,min((elbow-shoulder).length,along))
  lower_clamped=max(0.,min((wrist-elbow).length,(v.co-elbow).dot(lower_axis)))
  sleeve_distance=min((v.co-shoulder-upper_axis*upper_clamped).length,
                      (v.co-elbow-lower_axis*lower_clamped).length)
  if sleeve_distance>.117 and arm_sum>.001 and V[i,2]<1.43:
   release=smooth(.117,.175,sleeve_distance)*(1-smooth(.16,.28,sign*V[i,0]))
   if release>.001:
    torso={n:w for n,w in old.items() if n not in (upper,lower,hand,clavicle)}
    amount=sum(torso.values())
    torso={n:w/amount for n,w in torso.items()} if amount>1e-4 else {'Spine1':1.}
    old=mix(old,torso,release)
    setweights(i,old)
    arm_sum=sum(old.get(n,0) for n in (upper,lower,hand,clavicle))
  sleeve_core=smooth(.035,.135,along)*(1-smooth(.08,.13,radial_distance))*smooth(.20,.29,sign*V[i,0])
  arm_mask=max(smooth(.20,.72,arm_sum),sleeve_core)
  if arm_mask<.001:continue
  # Keep the sleeve attached rigidly along most of each segment. Only the
  # immediate elbow crease should compress as the forearm bends.
  elbow_mix=smooth(-.052,.061,longitudinal)
  wrist_mix=smooth(-.060,.024,(v.co-wrist).dot(lower_axis))*.92
  shoulder_mix=(1-smooth(-.018,.075,along))*.20
  sleeve_weights={
   clavicle:shoulder_mix,
   upper:(1-shoulder_mix)*(1-elbow_mix),
   lower:(1-shoulder_mix)*elbow_mix*(1-wrist_mix),
   hand:(1-shoulder_mix)*elbow_mix*wrist_mix,
  }
  setweights(i,mix(old,sleeve_weights,arm_mask))

 # Use a continuous spatial weight field across the armpit. Vertices a few
 # millimetres apart can belong to different scan fragments and therefore
 # have very different topology-based weights before this correction.
 for v in mesh.data.vertices:
  i=v.index
  if i in hands or i in seam or i not in other:continue
  x,y,z=v.co
  offset=sign*(x-shoulder.x)
  if sign*x<.10 or offset>.175 or not 1.18<z<1.565:continue
  blend=smooth(1.18,1.27,z)*(1-smooth(.088,.165,offset))
  blend*=smooth(.10,.15,sign*x)
  if blend<.001:continue
  underarm=1-smooth(1.34,1.46,z)
  arm_part=smooth(-.017+.018*underarm,.101+.026*underarm,offset)*(1-smooth(1.49,1.56,z))
  shoulder_part=max(0.,4*arm_part*(1-arm_part))*.16
  spine_part=1-arm_part-shoulder_part
  upper_chest=smooth(1.22,1.37,z)
  target={upper:arm_part,clavicle:shoulder_part,'Spine1':spine_part*upper_chest,'Spine':spine_part*(1-upper_chest)}
  old={mesh.vertex_groups[g.group].name:g.weight for g in v.groups}
  setweights(i,mix(old,target,blend))
mesh.data.update();fit_report['sleeve_vertices_transferred']=changed
fit_report['matching_neck_seam_vertices']=len(seam)
fit_report['finger_vertices']=sum(1 for v in mesh.data.vertices if any('Hand' in mesh.vertex_groups[g.group].name and not mesh.vertex_groups[g.group].name.endswith(('Hand','HandProp')) and g.weight>.01 for g in v.groups))
open(os.path.join(OUT,'hand_fit_report.json'),'w').write(json.dumps(fit_report,indent=2));print('MARTA_SKINNING',fit_report,flush=True)
