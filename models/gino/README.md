# Gino's 3D model

`gino/static/models/gino.glb` is made by these two scripts with Blender (as a Python module, no window needed):

```
python3.13 -m venv /opt/bvenv && /opt/bvenv/bin/pip install bpy==5.1.2 scikit-image
/opt/bvenv/bin/python sdf_gino.py 0.0055 high.npz        # sculpt: body shapes -> detailed mesh (~700k triangles)
WEBP=1 /opt/bvenv/bin/python build.py high.npz out       # light mesh (18k triangles), baked colour + normal maps,
                                                         # eyes, eyelids, skeleton, idle/walk/eat/sleep -> out/gino.glb
npx @gltf-transform/cli quantize out/gino.glb ../../gino/static/models/gino.glb   # ~0.6 MB
```

- Vertex colour R on the body = how long the fur is there (the website grows fur shells from it).
- Bone names used by the site (`kit.js`, `realGino`): neck, head, ear.L/R, lid.L/R, arm/forearm/hand.L/R, thigh/shin.L/R.
- The website moves the bones itself from the old puppet groups, so the baked animations are only for previews.
- `?oldgino` on any page shows the old shapes-only Gino; it's also the automatic backup if the file can't load.
