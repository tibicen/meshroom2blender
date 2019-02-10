# meshroom2blender
Blender importer of meshroom datafiles: cameras, images, sparse pointcloud and obj's.

Basic implementation of meshroom importer. If you have sphisticated node three it will use only the first nodes from the file.
Addon assumes you did compute each stages/nodes, and the output is same.

## Usage
Important note: For sparse point cloud to import you should change in `StructurefromMotion` node output: `Inter File Extension` to `.ply` format.
`File > Import > Import Meshroom` or [F3] Import Meshroom. Then select Meshroom working file .mg.

## Settings
- Imports Views `{StructureFromMotion}`
  - imports images if use undisorted then uses node `{PrepareDenseScene}`
  - creates cameras
- Imports Sparse point cloud `{StructureFromMotion}`
- Imports Dense mesh (instead of dense point cloud) `{Meshing}`
- Imports textured mesh `{Texturing}`

Additional option: by searching [F3] for `Meshroom update cameras`, you can copy settings from active camera to all meshroom cameras.

## TODO:
- seach through node tree and give option which elements import;
- if node is not computed then put some info about it;
- use undisorted images.
