using System;
using System.IO;
using System.Linq;
using System.Collections.Generic;
using UnityEngine;
using UnityEditor;
using UnityEngine.Rendering;

public static class AlatristeFinalBuild {
 [Serializable] class NativeBone { public string name; public string parent; public Vector3 position; public Quaternion rotation; public Vector3 scale; }
 [Serializable] class NativeSkeleton { public string character; public NativeBone[] bones; }
 [Serializable] class PreviewMesh { public Vector3[] vertices; public int[] triangles; }
 static GameObject MakeMartaSkeleton() {
  var data=JsonUtility.FromJson<NativeSkeleton>(File.ReadAllText(D+"Editor/MartaSkeleton.json"));
  var go=new GameObject("Skin");var map=new Dictionary<string,Transform>();
  foreach(var b in data.bones) {
   var t=new GameObject(b.name).transform;t.SetParent(string.IsNullOrEmpty(b.parent)?go.transform:map[b.parent],false);
   t.localPosition=b.position;t.localRotation=b.rotation;t.localScale=b.scale;map[b.name]=t;
  }
  if(map.Count!=68)throw new Exception("Expected Marta's 68 joints");return go;
 }
 const string D="Assets/AlatristeMod/";
 static string Root {get{return Path.GetFullPath(Path.Combine(Application.dataPath,"../.."));}}
 static void Texture(string name,bool normal=false) {
  var t=(TextureImporter)AssetImporter.GetAtPath(D+name);
  var textureType=normal?TextureImporterType.NormalMap:TextureImporterType.Default;
  bool srgb=name.Contains("BaseColor");
  if(t.maxTextureSize==4096&&t.textureType==textureType&&t.sRGBTexture==srgb&&
     t.alphaSource==TextureImporterAlphaSource.None&&t.textureCompression==TextureImporterCompression.CompressedHQ&&
     t.compressionQuality==100&&t.anisoLevel==8)return;
  t.maxTextureSize=4096;t.textureType=textureType;
  t.sRGBTexture=srgb;t.alphaSource=TextureImporterAlphaSource.None;
  t.textureCompression=TextureImporterCompression.CompressedHQ;t.compressionQuality=100;t.anisoLevel=8;t.SaveAndReimport();
 }
 static bool IsFppArmBone(string name) {
  return (name.StartsWith("Left")||name.StartsWith("Right")) &&
   (name.Contains("Arm")||name.Contains("Hand"));
 }
 static float FppArmWeight(BoneWeight w,Transform[] bones) {
  float total=0;
  if(w.weight0>0&&IsFppArmBone(bones[w.boneIndex0].name))total+=w.weight0;
  if(w.weight1>0&&IsFppArmBone(bones[w.boneIndex1].name))total+=w.weight1;
  if(w.weight2>0&&IsFppArmBone(bones[w.boneIndex2].name))total+=w.weight2;
  if(w.weight3>0&&IsFppArmBone(bones[w.boneIndex3].name))total+=w.weight3;
  return total;
 }
 static void SetCameraClearanceMask(Mesh mesh,Transform[] bones) {
  // Red selects the jacket region. Alpha protects the animated sleeves,
  // hands and fingers from the larger clearance used around the torso.
  var vertices=mesh.vertices;
  mesh.colors32=mesh.boneWeights.Select((w,i)=>{
   float arm=Mathf.SmoothStep(0,1,Mathf.InverseLerp(.22f,.80f,FppArmWeight(w,bones)));
   float jacket=Mathf.SmoothStep(0,1,Mathf.InverseLerp(.82f,1.12f,vertices[i].y));
   return new Color32((byte)Mathf.RoundToInt(jacket*255),255,255,(byte)Mathf.RoundToInt(arm*255));
  }).ToArray();
 }
 public static void Build() {
  AssetDatabase.Refresh();Texture("Alatriste_BaseColor.png");Texture("Alatriste_Normal.png",true);Texture("Alatriste_ORM.png");
  var importer=(ModelImporter)AssetImporter.GetAtPath(D+"Skin.fbx");
  if(!importer.isReadable||importer.importAnimation||importer.animationType!=ModelImporterAnimationType.Generic||
     importer.optimizeGameObjects||importer.meshCompression!=ModelImporterMeshCompression.Off||
     importer.indexFormat!=ModelImporterIndexFormat.UInt32||importer.materialImportMode!=ModelImporterMaterialImportMode.None) {
   importer.isReadable=true;importer.importAnimation=false;importer.animationType=ModelImporterAnimationType.Generic;
   importer.optimizeGameObjects=false;importer.meshCompression=ModelImporterMeshCompression.Off;
   importer.indexFormat=ModelImporterIndexFormat.UInt32;importer.materialImportMode=ModelImporterMaterialImportMode.None;importer.SaveAndReimport();
  }
  var shader=Shader.Find("Alatriste/DetailedTwoSided");if(shader==null)throw new Exception("Detailed shader missing");
  var mat=AssetDatabase.LoadAssetAtPath<Material>(D+"AlatristeDetailed.mat");
  if(mat==null){mat=new Material(shader);AssetDatabase.CreateAsset(mat,D+"AlatristeDetailed.mat");}mat.shader=shader;
  mat.SetTexture("_MainTex",AssetDatabase.LoadAssetAtPath<Texture2D>(D+"Alatriste_BaseColor.png"));
  mat.SetTexture("_BumpMap",AssetDatabase.LoadAssetAtPath<Texture2D>(D+"Alatriste_Normal.png"));
  mat.SetTexture("_ORM",AssetDatabase.LoadAssetAtPath<Texture2D>(D+"Alatriste_ORM.png"));mat.SetFloat("_BumpScale",.7f);
  mat.SetFloat("_HeadCameraRadius",0);EditorUtility.SetDirty(mat);
  var headMat=AssetDatabase.LoadAssetAtPath<Material>(D+"AlatristeHead.mat");
  if(headMat==null){headMat=new Material(mat);AssetDatabase.CreateAsset(headMat,D+"AlatristeHead.mat");}
  headMat.shader=shader;headMat.CopyPropertiesFromMaterial(mat);
  headMat.SetFloat("_HeadCameraRadius",.30f);EditorUtility.SetDirty(headMat);
  var source=UnityEngine.Object.Instantiate(AssetDatabase.LoadAssetAtPath<GameObject>(D+"Skin.fbx"));
  var skin=MakeMartaSkeleton();
  var map=skin.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name,t=>t);
  foreach(var a in skin.GetComponentsInChildren<Animator>())UnityEngine.Object.DestroyImmediate(a);
  foreach(var a in skin.GetComponentsInChildren<Animation>())UnityEngine.Object.DestroyImmediate(a);
  int triangles=0;float maxRotDifference=0;int rigidHeadCount=0;
  foreach(var r in source.GetComponentsInChildren<SkinnedMeshRenderer>()) {
   bool head=r.name.Contains("Head");
   var child=new GameObject(head?"AlatristeHead":"AlatristeBody");
   var parent=head?map["Head"]:skin.transform;child.transform.SetParent(parent,false);
   var mesh=UnityEngine.Object.Instantiate(r.sharedMesh);mesh.name=child.name;
   var matrix=parent.worldToLocalMatrix*r.transform.localToWorldMatrix;
   var normalMatrix=matrix.inverse.transpose;var v=mesh.vertices;var n=mesh.normals;var tang=mesh.tangents;
   for(int i=0;i<v.Length;i++) {
    v[i]=matrix.MultiplyPoint3x4(v[i]);if(n.Length==v.Length)n[i]=normalMatrix.MultiplyVector(n[i]).normalized;
    if(tang.Length==v.Length){var q=matrix.MultiplyVector(new Vector3(tang[i].x,tang[i].y,tang[i].z)).normalized;tang[i]=new Vector4(q.x,q.y,q.z,tang[i].w*(matrix.determinant<0?-1:1));}
   }
   mesh.vertices=v;if(n.Length==v.Length)mesh.normals=n;if(tang.Length==v.Length)mesh.tangents=tang;
   if(matrix.determinant<0)for(int s=0;s<mesh.subMeshCount;s++){var t=mesh.GetTriangles(s);for(int i=0;i<t.Length;i+=3){int q=t[i];t[i]=t[i+1];t[i+1]=q;}mesh.SetTriangles(t,s);}
   mesh.RecalculateBounds();triangles+=mesh.triangles.Length/3;
   string path=D+child.name+".asset";var existing=AssetDatabase.LoadAssetAtPath<Mesh>(path);
   if(head) {
    // A MeshRenderer parented to Head cannot be deformed by skin weights,
    // facial animation, jaw transforms or blend shapes.
    mesh.boneWeights=new BoneWeight[0];mesh.bindposes=new Matrix4x4[0];rigidHeadCount=v.Length;
   }else {
    var bones=r.bones.Select(b=>map[b.name]).ToArray();mesh.bindposes=bones.Select(b=>b.worldToLocalMatrix*child.transform.localToWorldMatrix).ToArray();
    SetCameraClearanceMask(mesh,bones);
    for(int i=0;i<bones.Length;i++)maxRotDifference=Mathf.Max(maxRotDifference,Quaternion.Angle(r.bones[i].rotation,bones[i].rotation));
   }
   if(existing==null){AssetDatabase.CreateAsset(mesh,path);existing=mesh;}else{EditorUtility.CopySerialized(mesh,existing);UnityEngine.Object.DestroyImmediate(mesh);EditorUtility.SetDirty(existing);}
   if(head){child.AddComponent<MeshFilter>().sharedMesh=existing;child.AddComponent<MeshRenderer>().sharedMaterials=Enumerable.Repeat(headMat,existing.subMeshCount).ToArray();}
   else {
    var bones=r.bones.Select(b=>map[b.name]).ToArray();
    var smr=child.AddComponent<SkinnedMeshRenderer>();smr.sharedMesh=existing;smr.bones=bones;smr.rootBone=map["Root"];smr.sharedMaterials=Enumerable.Repeat(mat,existing.subMeshCount).ToArray();smr.quality=SkinQuality.Bone4;smr.updateWhenOffscreen=true;smr.localBounds=new Bounds(new Vector3(0,1,0),Vector3.one*5);
   }
  }
  if(rigidHeadCount<1000)throw new Exception("Rigid head is missing");
  if(skin.GetComponentsInChildren<SkinnedMeshRenderer>().Length!=1)throw new Exception("Expected one deforming body");
  AlatristeFppBuilder.Attach(skin);
  PrefabUtility.SaveAsPrefabAsset(skin,D+"Skin.prefab");UnityEngine.Object.DestroyImmediate(source);UnityEngine.Object.DestroyImmediate(skin);AssetDatabase.SaveAssets();
  MakeSelectorPortrait();AssetDatabase.ImportAsset(D+"Skin_pic.png",ImportAssetOptions.ForceUpdate);
  var pic=(TextureImporter)AssetImporter.GetAtPath(D+"Skin_pic.png");pic.textureType=TextureImporterType.Sprite;pic.spriteImportMode=SpriteImportMode.Single;pic.maxTextureSize=1024;pic.alphaSource=TextureImporterAlphaSource.FromInput;pic.alphaIsTransparency=true;pic.SaveAndReimport();
  var go=new GameObject("Skin_pic",typeof(RectTransform),typeof(UnityEngine.UI.Image));go.layer=5;go.GetComponent<UnityEngine.UI.Image>().sprite=AssetDatabase.LoadAssetAtPath<Sprite>(D+"Skin_pic.png");go.GetComponent<UnityEngine.UI.Image>().preserveAspect=true;
  go.GetComponent<UnityEngine.UI.Image>().raycastTarget=false;go.GetComponent<RectTransform>().sizeDelta=new Vector2(2160,3840);PrefabUtility.SaveAsPrefabAsset(go,D+"Skin_pic.prefab");UnityEngine.Object.DestroyImmediate(go);
  ValidateAndRender();
  var outDir=Path.Combine(Root,"mod_alatriste");Directory.CreateDirectory(outDir);
  var builds=new[]{new AssetBundleBuild{assetBundleName="skin_marta_alatriste",assetNames=new[]{D+"Skin.prefab"}},new AssetBundleBuild{assetBundleName="pic_marta_alatriste",assetNames=new[]{D+"Skin_pic.prefab"}}};
  if(BuildPipeline.BuildAssetBundles(outDir,builds,BuildAssetBundleOptions.ChunkBasedCompression,BuildTarget.StandaloneWindows64)==null)throw new Exception("Bundle build failed");
  foreach(var name in new[]{"skin_marta_alatriste","pic_marta_alatriste"}) {var b=AssetBundle.LoadFromFile(Path.Combine(outDir,name));if(b==null)throw new Exception("Bundle load failed");if(b.LoadAllAssets<GameObject>().Length!=1)throw new Exception("Prefab count invalid");b.Unload(true);}
  File.WriteAllText(Path.Combine(Root,"unity_build_report.txt"),"Source: alatriste_img.glb\nCharacter: Marta only (native Mafra5/Marfa rig)\nUnity "+Application.unityVersion+"\nTriangles: "+triangles+"\nRigid head MeshRenderer vertices: "+rigidHeadCount+"\nNative Marta skeleton: 68 joints, original local positions/rotations/scales.\nHand and sleeve weights adapted from Marta's local reference; finger articulation enabled.\n4K PBR maps, readable body mesh, four bone weights per vertex.\nSelector portrait: transparent background.\nBoth Marta-specific bundles loaded successfully.\n");
  Debug.Log("ALATRISTE_MARTA_BUILD_OK");
 }
 static void MakeSelectorPortrait() {
  AlatristeBuild.MakeScene();var camera=UnityEngine.Object.FindObjectOfType<Camera>();camera.backgroundColor=new Color(0,0,0,0);camera.clearFlags=CameraClearFlags.SolidColor;
  var map=GameObject.Find("Skin").GetComponentsInChildren<Transform>().ToDictionary(t=>t.name,t=>t);var sword=PreviewSword(map);
  GuardPose(map);CloseFingers(map,"Right");CloseFingers(map,"Left");camera.orthographicSize=1.12f;
  Capture("Alatriste_Marta_selector",camera,new Vector3(-.55f,1.02f,4),true,1024,1536);
  File.Copy(Path.Combine(Root,"Alatriste_Marta_selector.png"),D+"Skin_pic.png",true);UnityEngine.Object.DestroyImmediate(sword);
 }
 static void Capture(string name,Camera cam,Vector3 position,bool transparent=false,int width=1000,int height=1200,Vector3? target=null) {
  // Editor camera renders can reuse cached skinning when no player frame ran.
  // Render the current bone matrices explicitly for deterministic pose QA.
  var temps=new List<GameObject>();var meshes=new List<Mesh>();var renderers=UnityEngine.Object.FindObjectsOfType<SkinnedMeshRenderer>();
  foreach(var r in renderers) {
   var m=UnityEngine.Object.Instantiate(r.sharedMesh);var verts=m.vertices;var norms=m.normals;var bw=m.boneWeights;var bp=m.bindposes;
   var matrices=r.bones.Select((b,i)=>r.transform.worldToLocalMatrix*b.localToWorldMatrix*bp[i]).ToArray();
   for(int i=0;i<verts.Length;i++) {
    var w=bw[i];Vector3 p=Vector3.zero,n=Vector3.zero;
    int[] ids={w.boneIndex0,w.boneIndex1,w.boneIndex2,w.boneIndex3};float[] ws={w.weight0,w.weight1,w.weight2,w.weight3};
    for(int k=0;k<4;k++)if(ws[k]>0){p+=matrices[ids[k]].MultiplyPoint3x4(verts[i])*ws[k];if(norms.Length==verts.Length)n+=matrices[ids[k]].MultiplyVector(norms[i])*ws[k];}
    if(float.IsNaN(p.x)||p.magnitude>10)throw new Exception("Invalid deformed body vertex");verts[i]=p;if(norms.Length==verts.Length)norms[i]=n.normalized;
   }
   m.vertices=verts;if(norms.Length==verts.Length)m.normals=norms;m.RecalculateBounds();
   var o=new GameObject("PoseValidationMesh");o.transform.SetParent(r.transform,false);o.AddComponent<MeshFilter>().sharedMesh=m;o.AddComponent<MeshRenderer>().sharedMaterials=r.sharedMaterials;r.enabled=false;temps.Add(o);meshes.Add(m);
  }
  cam.transform.position=position;cam.transform.LookAt(target??new Vector3(0,1,0));var rt=new RenderTexture(width,height,24,RenderTextureFormat.ARGB32);cam.targetTexture=rt;cam.Render();RenderTexture.active=rt;var t=new Texture2D(width,height,transparent?TextureFormat.RGBA32:TextureFormat.RGB24,false);t.ReadPixels(new Rect(0,0,width,height),0,0);t.Apply();File.WriteAllBytes(Path.Combine(Root,name+".png"),t.EncodeToPNG());cam.targetTexture=null;RenderTexture.active=null;UnityEngine.Object.DestroyImmediate(rt);UnityEngine.Object.DestroyImmediate(t);
  foreach(var r in renderers)r.enabled=true;foreach(var o in temps)UnityEngine.Object.DestroyImmediate(o);foreach(var m in meshes)UnityEngine.Object.DestroyImmediate(m);
 }
 static void Aim(Dictionary<string,Transform> bones,string bone,string child,Vector3 direction){var b=bones[bone];b.rotation=Quaternion.FromToRotation(bones[child].position-b.position,direction)*b.rotation;}
 static void GuardPose(Dictionary<string,Transform> map) {
  Aim(map,"RightArm","RightForeArm",new Vector3(.3f,-.25f,.7f));Aim(map,"RightForeArm","RightHand",new Vector3(-.05f,.05f,.85f));
  Aim(map,"LeftArm","LeftForeArm",new Vector3(-.2f,-.6f,-.1f));Aim(map,"LeftForeArm","LeftHand",new Vector3(.1f,-.6f,-.2f));
 }
 static void CloseFingers(Dictionary<string,Transform> map,string side) {
  float sign=side=="Right"?1:-1;
  foreach(var finger in new[]{"Index","Middle","Ring","Pinky"}) {
   float a=finger=="Index"?50:finger=="Pinky"?65:58;
   for(int j=1;j<=3;j++)map[side+"Hand"+finger+j].localRotation*=Quaternion.AngleAxis(sign*(j==1?a:j==2?72:40),Vector3.forward);
  }
  map[side+"HandThumb2"].localRotation*=Quaternion.AngleAxis(sign*30,Vector3.forward);
  map[side+"HandThumb3"].localRotation*=Quaternion.AngleAxis(sign*30,Vector3.forward);
 }
 [MenuItem("Alatriste/Probar agarre de Marta")]
 public static void TestMartaGrip() {
  AlatristeBuild.MakeScene();var map=GameObject.Find("Skin").GetComponentsInChildren<Transform>().ToDictionary(t=>t.name,t=>t);
  PreviewSword(map);GuardPose(map);CloseFingers(map,"Right");CloseFingers(map,"Left");SceneView.RepaintAll();
 }
 static GameObject PreviewSword(Dictionary<string,Transform> map) {
  // Reference is local QA only. Neither this geometry nor the game reference
  // files are included in the Skin prefab or the Nexus bundles.
  string path=Path.Combine(Root,"game_reference/CupRapierPreview.json");if(!File.Exists(path))return null;
  var data=JsonUtility.FromJson<PreviewMesh>(File.ReadAllText(path));var parent=map["RightHandProp"];var verts=data.vertices;
  for(int i=0;i<verts.Length;i++)verts[i]=parent.InverseTransformPoint(verts[i]);
  var mesh=new Mesh();mesh.vertices=verts;mesh.triangles=data.triangles;mesh.RecalculateNormals();mesh.RecalculateBounds();
  var obj=new GameObject("MartaSword_QA_Only");obj.hideFlags=HideFlags.DontSave;obj.transform.SetParent(parent,false);obj.AddComponent<MeshFilter>().sharedMesh=mesh;
  var mat=new Material(Shader.Find("Standard"));mat.color=new Color(.45f,.47f,.5f);mat.SetFloat("_Metallic",.8f);mat.SetFloat("_Glossiness",.45f);obj.AddComponent<MeshRenderer>().sharedMaterial=mat;return obj;
 }
 public static void ValidateAndRender() {
  AlatristeBuild.MakeScene();var skin=GameObject.Find("Skin");var map=skin.GetComponentsInChildren<Transform>().ToDictionary(t=>t.name,t=>t);var saved=map.ToDictionary(k=>k.Key,k=>k.Value.localRotation);var cam=UnityEngine.Object.FindObjectOfType<Camera>();cam.orthographicSize=1.18f;
  Capture("Alatriste_Unity_preview",cam,new Vector3(0,1,4));
  foreach(var s in new[]{"Left","Right"}){float sign=s=="Left"?-1:1;Aim(map,s+"Arm",s+"ForeArm",new Vector3(sign*.7f,.7f,0));Aim(map,s+"ForeArm",s+"Hand",new Vector3(sign*.5f,.7f,.3f));}
  Capture("Alatriste_Unity_arms_up",cam,new Vector3(0,1,4));Capture("Alatriste_Unity_arms_up_back",cam,new Vector3(0,1,-4));
  foreach(var kv in saved)map[kv.Key].localRotation=kv.Value;
  Aim(map,"RightArm","RightForeArm",new Vector3(-.25f,-.25f,.7f));Aim(map,"RightForeArm","RightHand",new Vector3(.15f,.15f,.8f));
  Capture("Alatriste_Unity_guard",cam,new Vector3(-2,1,4));
  foreach(var kv in saved)map[kv.Key].localRotation=kv.Value;
  var sword=PreviewSword(map);GuardPose(map);CloseFingers(map,"Right");CloseFingers(map,"Left");
  Capture("Alatriste_Marta_grip",cam,new Vector3(-1.5f,1.1f,4));
  cam.orthographic=false;cam.fieldOfView=65f;cam.nearClipPlane=.03f;
  var eye=map["Head"].position+new Vector3(0,.09f,.07f);
  Capture("Alatriste_Marta_fpp",cam,eye,false,1280,720,eye+new Vector3(0,-.34f,1));
  Capture("Alatriste_Marta_fpp_down",cam,eye,false,1280,720,eye+new Vector3(0,-1,.44f));
  Capture("Alatriste_Marta_fpp_wide",cam,new Vector3(-1.4f,1.4f,3.2f),false,1080,1080);
  cam.orthographic=true;
  var prop=map["RightHandProp"];cam.orthographicSize=.19f;Capture("Alatriste_Marta_hand_closeup",cam,prop.position+new Vector3(.3f,.2f,.65f),false,1000,1000,prop.position);cam.orthographicSize=1.18f;
  map["RightForeArm"].localRotation*=Quaternion.AngleAxis(65,Vector3.right);Capture("Alatriste_Marta_pronation",cam,new Vector3(-1.5f,1.1f,4));
  UnityEngine.Object.DestroyImmediate(sword);foreach(var kv in saved)map[kv.Key].localRotation=kv.Value;
  map["Head"].localRotation*=Quaternion.Euler(20,40,15);Capture("Alatriste_Unity_head_test",cam,new Vector3(0,1,4));
  foreach(var kv in saved)map[kv.Key].localRotation=kv.Value;
  UnityEditor.SceneManagement.EditorSceneManager.SaveScene(UnityEngine.SceneManagement.SceneManager.GetActiveScene(),D+"AlatristePreview.unity");
 }
}
