# MIT License

# Copyright (c) 2023 Nate Simon

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# File author: Nate Simon

"""

The purpose of this script is to fuse depth images and poses into a 3D reconstruction.
Here, we use Open3D's tensor reconstruction system: the VoxelBlockGrid.

The following are saved to file:
│   ├── 3D Reconstruction # After fusion, reconstruction and camera poses are saved to file

"""

import numpy as np
import time
import os

import open3d as o3d
from PIL import Image
import numpy as np
import yaml
from utils.utils import *
#####################################################################

addPose = True

CONFIG_PATH = "config.yaml"
config = read_yaml(CONFIG_PATH)

data_dir = config["data_dir"] # parent directory to look for RGB images, and save depth images

source = config["camera_source"] # meaning: crazyflie images have been undistorted to match kinect
rgb_dir = data_dir + "/" + source + "-rgb-images/"
depth_dir = data_dir + "/" + source + "-depth-images"
pose_dir = data_dir + "/crazyflie-poses/"
#####################################################################

# Initialize TSDF VoxelBlockGrid
depth_scale = config["VoxelBlockGrid"]["depth_scale"]
depth_max = config["VoxelBlockGrid"]["depth_max"]
trunc_voxel_multiplier = config["VoxelBlockGrid"]["trunc_voxel_multiplier"]
weight_threshold = config["weight_threshold"] # for planning and visualization (!! important !!)
device = config["VoxelBlockGrid"]["device"]

vbg = VoxelBlockGrid(depth_scale, depth_max, trunc_voxel_multiplier, o3d.core.Device(device))
        
#####################################################################

poses = [] # for visualization
t_start = time.time()

depth_files = [name for name in os.listdir(depth_dir) if os.path.isfile(os.path.join(depth_dir, name)) and name.endswith(".jpg")]
depth_files = sorted(depth_files)

# Get last frame
first_frame = split_filename(depth_files[0])
end_frame = split_filename(depth_files[-1])

for filename in depth_files:
    # Get the frame number from the depth filename
    frame_number = split_filename(filename)
    if frame_number == len(depth_files) - 1:
        continue
    print("Integrating frame %d/%d"%(frame_number,end_frame))
    # Get rbg_file
    rgb_file = rgb_dir + source + "_frame-%06d.rgb.jpg"%(frame_number)

    # Read in camera pose
    pose_file = data_dir + "/" + source + "-poses/" + source + "_frame-%06d.pose.txt"%(frame_number)
    cam_pose = np.loadtxt(pose_file)
    poses.append(cam_pose)

    # Get color image with Pillow and convert to RGB
    color = Image.open(rgb_file).convert("RGB")  # load

    # Integrate
    depth_file = depth_dir + "/" + source + "_frame-%06d.depth.npy"%(frame_number)
    depth_numpy = np.load(depth_file) # mm
    vbg.integration_step(color, depth_numpy, cam_pose)

#####################################################################
# Print out timing information
t_end = time.time()
print("Time taken (s): ", t_end - t_start)
print("FPS: ", end_frame/(t_end - t_start))

pcd = vbg.vbg.extract_point_cloud(weight_threshold)

if addPose:
    pose_lineset = get_poses_lineset(poses)
    visualizer = o3d.visualization.Visualizer()
    visualizer.create_window()
    visualizer.add_geometry(pcd.to_legacy())
    visualizer.add_geometry(pose_lineset)
    for pose in poses:
        # Add coordinate frame ( The x, y, z axis will be rendered as red, green, and blue arrows respectively.)
        coordinate_frame = o3d.geometry.TriangleMesh.create_coordinate_frame().scale(0.5, center=(0, 0, 0))
        visualizer.add_geometry(coordinate_frame.transform(pose))
    visualizer.run()
    visualizer.destroy_window()
else:
    o3d.visualization.draw([pcd])

#####################################################################

npz_filename = os.path.join(data_dir, "vbg.npz")
ply_filename = os.path.join(data_dir, "pointcloud.ply")
print('Saving npz to {}...'.format(npz_filename))
print('Saving ply to {}...'.format(ply_filename))

vbg.vbg.save(npz_filename)
o3d.io.write_point_cloud(ply_filename, pcd.to_legacy())

print('Saving finished')