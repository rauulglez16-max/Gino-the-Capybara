"""Blender pipeline: high sculpt -> light game mesh with baked colour + normal maps, eyes, lids, skeleton,
animations (idle, walk, eat, sleep) -> gino.glb.  Run: python build.py high.npz out_dir"""
import bpy, bmesh, numpy as np, math, sys, os
from mathutils import Vector, Matrix

HIGH, OUT = sys.argv[1], os.path.abspath(sys.argv[2])
TRIS = int(os.environ.get('TRIS', 18000)); TEX = int(os.environ.get('TEX', 1024))
os.makedirs(OUT, exist_ok=True)
bpy.ops.wm.read_factory_settings(use_empty=True)
sc = bpy.context.scene; vl = bpy.context.view_layer

def link(ob): sc.collection.objects.link(ob); return ob
def activate(*obs, active=None):
    for o in sc.objects:
        if o: o.select_set(False)
    for o in obs: o.select_set(True)
    vl.objects.active = active or obs[0]

HC, HS = np.array([0.72, 0, 1.02]), 1.1                  # head was sculpted 1.1x around this point
def head_pt(p): return HC + (np.asarray(p) - HC) * HS
EYE = {s: head_pt((0.955, s * 0.222, 1.205)) for s in (-1, 1)}

# ---------- high sculpt ----------
d = np.load(HIGH)
me = bpy.data.meshes.new('high'); me.from_pydata(d['verts'].tolist(), [], d['faces'].tolist()); me.update()
bm = bmesh.new(); bm.from_mesh(me); bmesh.ops.recalc_face_normals(bm, faces=bm.faces); bm.to_mesh(me); bm.free()
me.shade_smooth()
high = link(bpy.data.objects.new('high', me))

def srgb(c): c = np.asarray(c, float); return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)
def ss(e0, e1, x): t = np.clip((x - e0) / (e1 - e0), 0, 1); return t * t * (3 - 2 * t)

def fur_noise(P, seed=3, octaves=((7, .5), (17, .3), (41, .2))):
    rs = np.random.RandomState(seed); n = np.zeros(len(P))
    for f, a in octaves:
        for _ in range(4):
            dvec = rs.normal(size=3); dvec /= np.linalg.norm(dvec)
            n += a * np.sin(P @ dvec * f + rs.uniform(0, 6.3)) / 4
    return n

def regions(P, N):
    """Per-point colour (sRGB) and fur length, from where the point sits on Gino."""
    x, y, z = P.T; nz = N[:, 2]
    base = np.array([0.62, 0.42, 0.25])
    back = np.array([0.50, 0.32, 0.18]); belly = np.array([0.72, 0.56, 0.38])
    skin = np.array([0.17, 0.12, 0.09]); foot = np.array([0.20, 0.15, 0.12]); ear = np.array([0.30, 0.19, 0.12])
    col = np.tile(base, (len(P), 1)); L = np.ones(len(P))
    t = ss(0.85, 1.25, z) * ss(-0.2, 0.6, nz) * ss(1.25, 0.9, x)          # darker saddle along the back
    col = col * (1 - t[:, None]) + back * t[:, None]
    t = ss(0.75, 0.45, z) * ss(0.0, -0.6, nz) * (x < 0.8)                  # paler, softer belly
    col = col * (1 - t[:, None] * 0.45) + belly * t[:, None] * 0.45
    face = ss(0.95, 1.2, x) * ss(0.75, 0.9, z)                              # shorter fur on the face
    L = L - face * 0.55
    t = ss(1.30, 1.47, x) * 0.25                                             # muzzle front a shade darker
    for s in (-1, 1):                                                       # dark skin round the nostrils
        q = (P - head_pt((1.372, s * 0.062, 1.172))) / np.array([1.0, 2.2, 1.3]); t = np.maximum(t, ss(0.028, 0.01, np.linalg.norm(q, axis=1)) * 0.9)
    t = np.maximum(t, ss(1.25, 1.4, x) * ss(0.022, 0.008, np.abs(z - (0.915 + (x - 1.47) * 0.1))) * 0.6)   # lips
    col = col * (1 - t[:, None]) + skin * t[:, None]; L -= t * 0.5
    for s in (-1, 1):
        e = EYE[s]; r = np.linalg.norm(P - e, axis=1)
        t = ss(0.085, 0.05, r); col = col * (1 - t[:, None] * 0.7) + skin * t[:, None] * 0.7; L *= 1 - ss(0.075, 0.055, r)   # dark ring round each eye
        ec = head_pt((0.73, s * 0.175, 1.33)); r = np.linalg.norm(P - ec, axis=1)
        t = ss(0.08, 0.05, r); col = col * (1 - t[:, None]) + ear * t[:, None]; L = np.minimum(L, 1 - t * 0.8)
    t = ss(0.32, 0.12, z); L -= t * 0.35                                     # legs: shorter
    t = ss(0.11, 0.05, z); col = col * (1 - t[:, None]) + foot * t[:, None]; L = np.minimum(L, 1 - t)    # bare feet
    t = ss(0.04, 0.015, z) * ((x > 0.55) & (x < 0.7) | (x > -0.5) & (x < -0.38)); col = col * (1 - t[:, None] * 0.6)   # toenails
    n = fur_noise(P)
    col = col * (1 + 0.16 * n[:, None]) * (1 + 0.05 * np.array([1, 0.3, -0.5]) * n[:, None])
    return np.clip(col, 0, 1), np.clip(L, 0, 1)

P = np.array([v.co for v in me.vertices]); N = np.array([v.normal for v in me.vertices])
col, _ = regions(P, N)
ca = me.color_attributes.new('col', 'FLOAT_COLOR', 'POINT')
ca.data.foreach_set('color', np.c_[srgb(col), np.ones(len(col))].ravel().astype(np.float32))
mh = bpy.data.materials.new('highmat'); mh.use_nodes = True; nt = mh.node_tree
an = nt.nodes.new('ShaderNodeAttribute'); an.attribute_name = 'col'
nt.links.new(an.outputs['Color'], nt.nodes['Principled BSDF'].inputs['Base Color']); me.materials.append(mh)

# ---------- light game mesh ----------
low = link(bpy.data.objects.new('Gino', me.copy())); low.data.name = 'GinoBody'
low.data.materials.clear(); low.data.color_attributes.remove(low.data.color_attributes['col'])
dec = low.modifiers.new('dec', 'DECIMATE'); dec.ratio = TRIS / len(me.polygons)
activate(low); bpy.ops.object.modifier_apply(modifier='dec')
bpy.ops.object.mode_set(mode='EDIT'); bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.uv.smart_project(angle_limit=math.radians(60), island_margin=0.006); bpy.ops.object.mode_set(mode='OBJECT')
print('low tris', sum(len(p.vertices) - 2 for p in low.data.polygons))
# fur length per vertex for the website's fur shells (stored as vertex colour R)
P2 = np.array([v.co for v in low.data.vertices]); N2 = np.array([v.normal for v in low.data.vertices])
_, L2 = regions(P2, N2)
fa = low.data.color_attributes.new('furlen', 'BYTE_COLOR', 'POINT')
fa.data.foreach_set('color', np.c_[L2, L2, L2, np.ones(len(L2))].ravel().astype(np.float32))

def img(name, data=False):
    im = bpy.data.images.new(name, TEX, TEX, alpha=False, float_buffer=False)
    if data: im.colorspace_settings.name = 'Non-Color'
    return im
ml = bpy.data.materials.new('GinoFur'); ml.use_nodes = True; nt = ml.node_tree; bs = nt.nodes['Principled BSDF']
bs.inputs['Roughness'].default_value = 0.85
colimg, nrmimg = img('gino_color'), img('gino_normal', True)
tc = nt.nodes.new('ShaderNodeTexImage'); tc.image = colimg
tn = nt.nodes.new('ShaderNodeTexImage'); tn.image = nrmimg
nm = nt.nodes.new('ShaderNodeNormalMap')
low.data.materials.append(ml)

sc.render.engine = 'CYCLES'; sc.cycles.device = 'CPU'; sc.cycles.samples = 1
bk = sc.render.bake; bk.use_selected_to_active = True; bk.cage_extrusion = 0.03; bk.max_ray_distance = 0.06; bk.margin = 8
activate(high, low, active=low)
nt.nodes.active = tc; bk.use_pass_direct = bk.use_pass_indirect = False; bk.use_pass_color = True
bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'})
nt.nodes.active = tn; bpy.ops.object.bake(type='NORMAL')
for im in (colimg, nrmimg):
    im.filepath_raw = f'{OUT}/{im.name}.png'; im.file_format = 'PNG'; im.save()
tc.image = bpy.data.images.load(f'{OUT}/gino_color.png'); tn.image = bpy.data.images.load(f'{OUT}/gino_normal.png')
tn.image.colorspace_settings.name = 'Non-Color'
nt.links.new(tc.outputs['Color'], bs.inputs['Base Color'])
nt.links.new(tn.outputs['Color'], nm.inputs['Color']); nt.links.new(nm.outputs['Normal'], bs.inputs['Normal'])
bpy.data.objects.remove(high)

# ---------- eyes and eyelids ----------
def sphere(name, r, at, segs=24, rings=16, mat=None):
    m = bpy.data.meshes.new(name); b = bmesh.new()
    bmesh.ops.create_uvsphere(b, u_segments=segs, v_segments=rings, radius=r); b.to_mesh(m); b.free(); m.shade_smooth()
    o = link(bpy.data.objects.new(name, m)); o.location = Vector(at)
    if mat: m.materials.append(mat)
    return o
eyem = bpy.data.materials.new('GinoEye'); eyem.use_nodes = True; b = eyem.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (0.012, 0.007, 0.004, 1); b.inputs['Roughness'].default_value = 0.04
lidm = bpy.data.materials.new('GinoLid'); lidm.use_nodes = True; b = lidm.node_tree.nodes['Principled BSDF']
b.inputs['Base Color'].default_value = (*srgb([0.20, 0.13, 0.09]), 1); b.inputs['Roughness'].default_value = 0.8
eyes, lids = {}, {}
for s, side in ((1, 'L'), (-1, 'R')):
    c = EYE[s] + np.array([0.0, -s * 0.012, 0.0])
    eyes[side] = sphere(f'Eye.{side}', 0.043, c, mat=eyem)
    eyes[side].scale = (1.05, 0.8, 0.95)
    lid = sphere(f'Lid.{side}', 0.047, c, 20, 12, lidm)            # upper lid: top half of a slightly bigger ball
    bm = bmesh.new(); bm.from_mesh(lid.data)
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.z < -0.002], context='VERTS'); bm.to_mesh(lid.data); bm.free()
    lid.scale = (1.08, 0.82, 1.0); lids[side] = lid

# ---------- skeleton ----------
arm = bpy.data.armatures.new('GinoRig'); rig = link(bpy.data.objects.new('GinoRig', arm))
activate(rig); bpy.ops.object.mode_set(mode='EDIT')
def bone(name, h, t, parent=None, deform=True, roll=0):
    b = arm.edit_bones.new(name); b.head, b.tail = Vector(h), Vector(t); b.roll = roll; b.use_deform = deform
    if parent: b.parent = arm.edit_bones[parent]; b.use_connect = False
    return b
bone('root', (0, 0, 0), (0, 0, 0.25), deform=False)
bone('hips', (-0.15, 0, 0.82), (-0.75, 0, 0.86), 'root')
bone('chest', (-0.15, 0, 0.82), (0.42, 0, 0.86), 'hips')
bone('neck', (0.42, 0, 0.88), (0.74, 0, 1.04), 'chest')
bone('head', tuple(HC + [0.02, 0, 0.02]), tuple(head_pt((1.40, 0, 1.0))), 'neck')
for s, side in ((1, 'L'), (-1, 'R')):
    ep = head_pt((0.73, s * 0.175, 1.31))
    bone(f'ear.{side}', ep, ep + np.array([0, s * 0.02, 0.1]), 'head')
    bone(f'lid.{side}', EYE[s], EYE[s] + np.array([0.06, 0, 0]), 'head')
    y = s * 0.24
    bone(f'arm.{side}', (0.44, y, 0.66), (0.47, y, 0.22), 'chest')
    bone(f'forearm.{side}', (0.47, y, 0.22), (0.48, y, 0.06), f'arm.{side}')
    bone(f'hand.{side}', (0.48, y, 0.06), (0.6, y, 0.03), f'forearm.{side}')
    y = s * 0.27
    bone(f'thigh.{side}', (-0.58, s * 0.29, 0.72), (-0.63, y, 0.38), 'hips')
    bone(f'shin.{side}', (-0.63, y, 0.38), (-0.66, y, 0.07), f'thigh.{side}')
    bone(f'foot.{side}', (-0.66, y, 0.07), (-0.45, y, 0.03), f'shin.{side}')
bpy.ops.object.mode_set(mode='OBJECT')
# body skinned with automatic (heat) weights; lids/ears excluded from body heat by bone choice
lidb = arm.bones['lid.L'];
activate(low, rig, active=rig); bpy.ops.object.parent_set(type='ARMATURE_AUTO')
# lids must not pull the face: drop any lid weights from the body
for side in 'LR':
    vg = low.vertex_groups.get(f'lid.{side}')
    if vg: low.vertex_groups.remove(vg)
for side in 'LR':
    for o, bname in ((eyes[side], 'head'), (lids[side], f'lid.{side}')):
        mw = o.matrix_world.copy(); o.parent = rig; o.parent_type = 'BONE'; o.parent_bone = bname; o.matrix_world = mw

# ---------- animations ----------
pb = rig.pose.bones
for p in pb: p.rotation_mode = 'XYZ'
def key(frame, poses, loc=None):
    for p in pb: p.rotation_euler = (0, 0, 0); p.location = (0, 0, 0)
    for n, r in poses.items(): pb[n].rotation_euler = [math.radians(a) for a in r]
    if loc: pb['root'].location = loc
    for p in pb:
        p.keyframe_insert('rotation_euler', frame=frame); p.keyframe_insert('location', frame=frame)
# Axes (from the rest pose): legs swing about local Z (negative = foot forward); chest/neck/head pitch about
# local X (negative = nose down); lids turn about their own length (local Y); root lifts along local Y.
LIDUP = float(os.environ.get('LIDUP', 100))
def lidpose(a):        # a=1 open, 0 closed
    ang = -90 + (LIDUP + 90) * a
    return {'lid.L': (0, ang, 0), 'lid.R': (0, -ang, 0)}
def merge(*ds):
    out = {}
    for dd in ds:
        for k, v in dd.items(): out[k] = tuple(np.add(out.get(k, (0, 0, 0)), v))
    return out
def up(h): return (0, h, 0)
FPS = 24; sc.render.fps = FPS
anims = {}
def action(name, frames):
    act = bpy.data.actions.new(name); rig.animation_data_create(); rig.animation_data.action = act
    for f, poses, loc in frames: key(f, poses, loc)
    anims[name] = act
    return act
open_ = lidpose(1)
# idle: breathing, small head nods, ear flicks, one blink
action('idle', [(1, open_, None),
                (24, merge(open_, {'neck': (2, 0, 0), 'ear.L': (8, 0, 0)}), up(0.006)),
                (40, merge(open_, {'neck': (-1, 0, 0)}), None), (43, merge(lidpose(0.05), {'neck': (-1, 0, 0)}), None), (46, merge(open_, {'neck': (-1, 0, 0)}), None),
                (72, merge(open_, {'head': (-5, 0, 0), 'ear.R': (-8, 0, 0)}), up(0.006)),
                (96, open_, None)])
SW = float(os.environ.get('SWING', 24))
def walk(ph):
    a, b = math.sin(ph) * SW, math.sin(ph + math.pi) * SW          # a: FL + HR, b: FR + HL
    la, lb = max(0, math.cos(ph)) * 35, max(0, math.cos(ph + math.pi)) * 35   # lift the swinging foot
    return merge(open_, {'arm.L': (0, 0, -a), 'arm.R': (0, 0, -b), 'thigh.L': (0, 0, -b), 'thigh.R': (0, 0, -a),
                         'forearm.L': (0, 0, la), 'forearm.R': (0, 0, lb), 'shin.L': (0, 0, -lb * 0.8), 'shin.R': (0, 0, -la * 0.8),
                         'hand.L': (la * 0.6, 0, 0), 'hand.R': (lb * 0.6, 0, 0),
                         'neck': (math.sin(2 * ph) * 2, 0, 0), 'chest': (0, math.sin(ph) * 2.5, 0), 'hips': (0, math.sin(ph) * 2, 0)})
action('walk', [(1 + i * 3, walk(i / 8 * 2 * math.pi), up(abs(math.sin(i / 8 * 2 * math.pi)) * 0.018)) for i in range(9)])
down = {'neck': (-34, 0, 0), 'head': (-28, 0, 0), 'chest': (-5, 0, 0), 'arm.L': (0, 0, 5), 'arm.R': (0, 0, 5)}
action('eat', [(1, merge(open_, down), None), (6, merge(open_, down, {'head': (-6, 0, 0)}), None), (12, merge(open_, down), None),
               (18, merge(open_, down, {'head': (-6, 0, 3), 'ear.L': (6, 0, 0)}), None), (24, merge(open_, down), None)])
DROP = float(os.environ.get('DROP', -0.3))
tuck = {'arm.L': (0, 0, -30), 'arm.R': (0, 0, -30), 'forearm.L': (0, 0, 105), 'forearm.R': (0, 0, 105), 'hand.L': (0, 0, -60), 'hand.R': (0, 0, -60),
        'thigh.L': (0, 0, -70), 'thigh.R': (0, 0, -70), 'shin.L': (0, 0, 125), 'shin.R': (0, 0, 125), 'foot.L': (-40, 0, 0), 'foot.R': (-40, 0, 0),
        'neck': (-12, 0, 0), 'head': (-4, 0, 0), 'ear.L': (-6, 0, 0), 'ear.R': (6, 0, 0)}
sl = merge(lidpose(0), tuck)
action('sleep', [(1, sl, up(DROP)), (48, merge(sl, {'neck': (-2, 0, 0)}), up(DROP + 0.01)), (96, sl, up(DROP))])
# put each action on its own NLA track so the exporter writes them all
ad = rig.animation_data; ad.action = None
for name, act in anims.items():
    tr = ad.nla_tracks.new(); tr.name = name; st = tr.strips.new(name, 1, act); tr.mute = False
bpy.ops.wm.save_as_mainfile(filepath=f'{OUT}/gino.blend')
activate(rig, low, *eyes.values(), *lids.values(), active=rig)
bpy.ops.export_scene.gltf(filepath=f'{OUT}/gino.glb', export_format='GLB', use_selection=True,
                          export_animation_mode='NLA_TRACKS', export_image_format='WEBP' if os.environ.get('WEBP') else 'AUTO',
                          export_vertex_color='ACTIVE', export_all_vertex_colors=True)
print('exported', os.path.getsize(f'{OUT}/gino.glb'))
