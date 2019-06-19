from mathutils import Matrix, Vector
import bpy
import importlib
import sys
from math import pi
import os
import json
'''
Copyright (C) 2018 Dawid Huczyński
dawid.huczynski@gmail.com

Created by Dawid Huczyński

    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.

    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU General Public License for more details.

    You should have received a copy of the GNU General Public License
    along with this program.  If not, see <http://www.gnu.org/licenses/>.
'''

bl_info = {
    "name": "Meshroom importer",
    "description": "Imports from .mg file cameras, images, sparse and obj",
    "author": "Dawid Huczyński",
    "version": (0, 1, 0),
    "blender": (2, 80, 0),
    "location": "File > Import > Import Meshroom",
    "warning": "This addon is still in development.",
    "wiki_url": "",
    "category": "Import-Export"}


# module import https://github.com/uhlik/bpy/blob/master/view3d_point_cloud_visualizer.py
# thanks to Jakub Uhlik
vis_mod = 'view3d_point_cloud_visualizer'
if vis_mod in sys.modules.keys() and sys.modules[vis_mod].bl_info['version'] <= (0, 8, 11):
    local_visualizer = False
else:
    from . import view3d_point_cloud_visualizer as point_cloud
    point_cloud.register()
    local_visualizer = True


def find_view_layer(coll, lay_coll=None):
    if lay_coll is None:
        lay_coll = bpy.context.view_layer.layer_collection
    if lay_coll.collection == coll:
        return lay_coll
    else:
        for child in lay_coll.children:
            a = find_view_layer(coll, child)
            if a:
                return a
        return None


def get_meshroom_paths(filepath):
    'Handle meshroom file'
    cache = os.path.join(os.path.dirname(filepath), 'MeshroomCache')
    data = json.load(open(filepath, 'r'))
    data
    try:
        nodeSFM = data['graph']['StructureFromMotion_1']
        nodeType = nodeSFM['nodeType']
        uid0 = nodeSFM['uids']['0']
        # sfm = nodeSFM['outputs']['output'].format(
        #     cache=cache, nodeType=nodeType, uid0=uid0)
        cameras_sfm = nodeSFM['outputs']['outputViewsAndPoses'].format(
            cache=cache, nodeType=nodeType, uid0=uid0)
        # sparse = nodeSFM['outputs']['output'].format(
        #     cache=cache, nodeType=nodeType, uid0=uid0)
        sparse = nodeSFM['outputs']['extraInfoFolder'].format(
            cache=cache, nodeType=nodeType, uid0=uid0) + 'cloud_and_poses.ply'
    except KeyError:
        cameras_sfm = sparse = None
    try:
        prepDense = data['graph']['PrepareDenseScene_1']
        nodeType = prepDense['nodeType']
        uid0 = prepDense['uids']['0']
        exr_folder = prepDense['outputs']['output'].format(cache=cache, nodeType=nodeType, uid0=uid0)
    except KeyError:
        exr_folder = None
    try:
        nodeMesh = data['graph']['Meshing_1']
        dense_obj = nodeMesh['outputs']['output'].format(
            cache=cache, nodeType=nodeMesh['nodeType'], uid0=nodeMesh['uids']['0'])
    except KeyError:
        dense_obj = None
    try:
        nodeTex = data['graph']['Texturing_1']
        tex_obj = nodeTex['outputs']['outputMesh'].format(
            cache=cache, nodeType=nodeTex['nodeType'], uid0=nodeTex['uids']['0'])
    except KeyError:
        tex_obj = None
    return (cameras_sfm, sparse, dense_obj, tex_obj, exr_folder)


def import_cameras(cameras_sfm, img_depth, undistorted, exr_folder):
    'read camera sfm and imports to blender'
    data = json.load(open(cameras_sfm, 'r'))
    poses = {x['poseId']: x['pose'] for x in data['poses']}
    intrinsics = {x['intrinsicId']: x for x in data['intrinsics']}

    #TODO dimensions per camera
    render = bpy.context.scene.render
    render.resolution_x = int(data['views'][0]['width'])
    render.resolution_y = int(data['views'][0]['height'])

    for view in data['views']:
        view_id = view['viewId']
        if undistorted:
            path = os.path.join(exr_folder, f'{view_id}.exr')
        else:
            path = view['path']
        width, height = int(view['width']), int(view['height'])
        focal_length = float(view['metadata']['Exif:FocalLength'])
        pose = poses[view['poseId']]['transform']
        intrinsic = intrinsics[view['intrinsicId']]
        pxFocalLength = float(intrinsic['pxFocalLength'])
        principalPoint = [float(x) for x in intrinsic['principalPoint']]
        
        # camera
        bcam = bpy.data.cameras.new(f'View {view_id}')
        bcam.display_size = .25
        bcam.sensor_width = focal_length
        bcam.lens_unit = 'MILLIMETERS'
        bcam.lens = (pxFocalLength/max((width,height)))*focal_length
        bcam.shift_x = (principalPoint[0] - width/2)/width
        bcam.shift_y = (principalPoint[1] - height/2)/height
        
        # image
        bcam.show_background_images = True
        bg = bcam.background_images.new()
        bg.image = bpy.data.images.load(path)
        bg.display_depth = img_depth
        
        # camera object
        if undistorted:
            name = f'View {view_id}'
        else:
            name = 'View {}'.format(os.path.splitext(os.path.basename(path)))
        ob = bpy.data.objects.new(name, bcam)
        bpy.context.collection.objects.link(ob)
        loc = [float(x) for x in pose['center']]
        rot = [float(x) for x in pose['rotation']]
        rotation = [rot[:3], rot[3:6], rot[6:]]
        m = Matrix(rotation)
        ob.matrix_world = m.to_4x4() @ Matrix().Rotation(pi, 4, 'X')
        ob.location = Vector(loc)


def import_object(filepath):
    bpy.ops.import_scene.obj(filepath=filepath)
    bpy.context.selected_objects[0].matrix_world = Matrix()


class import_meshroom(bpy.types.Operator):
    bl_idname = "import_scene.meshroom"
    bl_label = "Import Meshroom"
    bl_description = "Imports cameras, images, sparse and obj from meshroom .mg file"
    # bl_options = {"REGISTER"}

    files: bpy.props.CollectionProperty(
        type=bpy.types.OperatorFileListElement,
        options={'HIDDEN', 'SKIP_SAVE'})

    directory: bpy.props.StringProperty(
        maxlen=1024, subtype='FILE_PATH', options={'HIDDEN', 'SKIP_SAVE'})

    import_views: bpy.props.BoolProperty(default=True, name='Views', description='Import views as cameras and images')
    
    undistorted: bpy.props.BoolProperty(default=True, name='Undistorted', description='Better, but heavy images')
    
    DEPTH = [
        ('FRONT', 'FRONT', 'Preview semi transparent image in front of the objects', '', 0),
        ('BACK', 'BACK', 'Preview image behing objects', '', 1)
    ]
    img_front: bpy.props.EnumProperty(items=DEPTH, name='Depth', description='', default='FRONT')

    import_sparse: bpy.props.BoolProperty(default=True, name='Import SFM', description='')

    import_dense: bpy.props.BoolProperty(default=False, name='Import dense mesh', description='')

    import_textured: bpy.props.BoolProperty(default=True, name='Import textured mesh', description='')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        file = self.files[0].name
        directory = self.directory
        filepath = os.path.join(directory, file)
        # container collection for import
        col = bpy.data.collections.new(file)
        camera_col = bpy.data.collections.new('Views')
        col.children.link(camera_col)
        context.scene.collection.children.link(col)
        lay_col = find_view_layer(camera_col)
        context.view_layer.active_layer_collection = lay_col
        # filepath = PATH
        cameras_sfm, sparse, dense_obj, tex_obj, exr_folder = get_meshroom_paths(filepath)
        if self.import_views:
            import_cameras(cameras_sfm, self.img_front, self.undistorted, exr_folder)
        lay_col = find_view_layer(col)
        context.view_layer.active_layer_collection = lay_col
        if self.import_sparse:
            if os.path.exists(sparse):
                empty = bpy.data.objects.new('sparse cloud SFM', None)
                col.objects.link(empty)
                empty.select_set(True)
                context.view_layer.objects.active = empty
                bpy.ops.point_cloud_visualizer.load_ply_to_cache(filepath=sparse)
                bpy.ops.point_cloud_visualizer.draw()
            elif os.path.exitsts(sparse.replace('.ply', '.abc')):
                self.report({'ERROR_INVALID_INPUT'}, "You need to use .ply format instead of .abc to use colored pointcloud. "\
                                                 "You can always import .abc through Blender alembic importer.")
            else:
                self.report({'ERROR_INVALID_INPUT'}, "Missing Meshroom reconstruction: StructureFromMotion (.ply format).")
        if self.import_dense:
            if dense_obj:
                import_object(dense_obj)
            else:
                self.report({'ERROR_INVALID_INPUT'}, "Missing Meshroom reconstruction: Meshing.")
        if self.import_textured and tex_obj:
            if tex_obj:
                import_object(tex_obj)
            else:
                self.report({'ERROR_INVALID_INPUT'}, "Missing Meshroom reconstruction: Texturing.")
        return {"FINISHED"}


class meshroom_update_focal(bpy.types.Operator):
    bl_idname = "view3d.update_focal"
    bl_label = "Meshroom: update focal"
    bl_description = "Updates Focal Length from active camera to other cameras"
    bl_options = {"REGISTER"}

    @classmethod
    def poll(cls, context):
        return True

    def execute(self, context):
        ob = context.active_object
        if ob.type == 'CAMERA':
            lens = ob.data.lens
            shift_x = ob.data.shift_x
            shift_y = ob.data.shift_y
            sensor_width = ob.data.sensor_width

            for cam in bpy.data.cameras:
                if cam.name.startswith('View '):
                    cam.lens = lens
                    cam.shift_x = shift_x
                    cam.shift_y = shift_y
                    cam.sensor_width = sensor_width
        return {"FINISHED"}


def import_meshroom_button(self, context):
    self.layout.operator(import_meshroom.bl_idname,
                         text="Import Meshroom")


classes = (
    import_meshroom,
    meshroom_update_focal,
)


def register():
    for cls in classes:
        bpy.utils.register_class(cls)

    bpy.types.TOPBAR_MT_file_import.append(import_meshroom_button)


def unregister():
    bpy.types.TOPBAR_MT_file_import.remove(import_meshroom_button)
    for cls in reversed(classes):
        bpy.utils.unregister_class(cls)

    if local_visualizer:
        point_cloud.unregister()


if __name__ == "__main__":
    register()
