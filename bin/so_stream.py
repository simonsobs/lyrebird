import argparse
import numpy as np
from spt3g import core
import yaml
import ast
from itertools import product
import sys


class FocalplaneConfig:
    def __init__(self, ndets=0):
        self.num_dets = ndets
        self.xs = [0 for _ in range(ndets)]
        self.ys = [0. for _ in range(ndets)]
        self.rots = [0. for _ in range(ndets)]
        self.cnames = ['' for _ in range(ndets)]
        self.eqs = ['' for _ in range(ndets)]
        self.cmaps = ['' for _ in range(ndets)]
        self.templates = ['' for _ in range(ndets)]

    def config_frame(self):
        frame = core.G3Frame(core.G3FrameType.Wiring)
        frame['x'] = core.G3VectorDouble(self.xs)
        frame['y'] = core.G3VectorDouble(self.ys)
        frame['rotation'] = core.G3VectorDouble(self.rots)
        frame['cname'] = core.G3VectorString(self.cnames)
        frame['equations'] = core.G3VectorString(self.eqs)
        frame['cmaps'] = core.G3VectorString(self.cmaps)
        frame['templates'] = core.G3VectorString(self.templates)
        return frame

    @classmethod
    def grid(cls, xdim, ydim, ygap=0):
        fp = cls()
        xs, ys, dis = range(xdim), range(ydim), range(4)
        cmaps = ["red_cmap", "bolo_blue_cmap"]
        for i, (y, x, di) in enumerate(product(ys, xs, dis)):
            color_idx, rot_idx = di//2, di%2
            name = f"channel_{i}"
            _y = y
            if ygap > 0:
                _y += 0.5 * (y // ygap)

            fp.xs.append(x)
            fp.ys.append(_y)
            fp.rots.append(np.pi / 2 * rot_idx)
            fp.cnames.append(name)
            fp.eqs.append(f"/ + 1 s {name} 2")
            fp.cmaps.append(cmaps[color_idx])
            fp.templates.append(f"template_c{color_idx}_p0")

        fp.num_dets = len(fp.xs)
        return fp

    @classmethod
    def from_wafer_file(cls, wafer_file, wafer_scale=50):
        import copy
        import quaternionarray as qa
        import toml

        dets = toml.load(wafer_file)
        fp = cls(ndets=len(dets))
        band_idxs = {}
        bands_seen = 0

        xaxis = np.array([1., 0., 0.])
        zaxis = np.array([0., 0., 1.])
        cmaps = ["red_cmap", "bolo_blue_cmap"]

        def det_coords(det):
            quat =np.array(det['quat']).astype(np.float64)
            rdir = qa.rotate(quat, zaxis).flatten()
            ang = np.arctan2(rdir[1], rdir[0])
            orient = qa.rotate(quat, xaxis).flatten()
            polang = np.arctan2(orient[1], orient[0])
            mag = np.arccos(rdir[2]) * 180 / np.pi
            xpos = mag * np.cos(ang)
            ypos = mag * np.sin(ang)
            return (xpos, ypos), polang

        for key, det in dets.items():
            chan = det['channel']
            (x, y), polangle = det_coords(det)

            if det['band'] not in band_idxs:
                band_idxs[det['band']] = bands_seen
                bands_seen += 1
            color_idx = band_idxs[det['band']]

            fp.xs[chan] = x * wafer_scale
            fp.ys[chan] = y * wafer_scale
            fp.rots[chan] = polangle
            fp.cnames[chan] = key
            fp.eqs[chan] = f"/ + 1 s {key} 2"
            fp.cmaps[chan] = cmaps[color_idx]
            fp.templates[chan] = f"template_c{color_idx}_p0"

        return fp


class SmurfVis:
    def __init__(self, target_rate=3, layout='grid', xdim=32, ydim=32, ygap=4,
                 wafer_file=None, wafer_scale=50):

        self.target_rate = target_rate
        if layout.lower() == 'grid':
            self.fp = FocalplaneConfig.grid(xdim, ydim, ygap=ygap)
        elif layout.lower() == 'wafer':
            self.fp = FocalplaneConfig.from_wafer_file(wafer_file, wafer_scale=wafer_scale)

        self.sent_cfg = False
        self.n = self.fp.num_dets
        self.mask = np.arange(self.n)  # rchan -> smurf channel mask

    def __call__(self, frame):
        out = []
        if not self.sent_cfg:
            out.append(self.fp.config_frame())
            self.sent_cfg = True

        if frame.type == core.G3FrameType.Wiring:
            mask_register = 'AMCc.SmurfProcessor.ChannelMapper.Mask'
            if mask_register in frame['status']:
                status = yaml.safe_load(frame['status'])
                self.mask = np.array(ast.literal_eval(status[mask_register]))

        if frame.type != core.G3FrameType.Scan:
            return out

        # Downsample the frame data, stolen from SmurfRecorder agent
        ds_factor = frame['data'].sample_rate / core.G3Units.Hz // self.target_rate
        if np.isnan(ds_factor):  # There is only one element in the timestream
            ds_factor = 1
        ds_factor = max(int(ds_factor), 1)  # Prevents downsample factors < 1

        sample_indices = np.arange(0, frame['data'].n_samples, ds_factor, dtype=np.int32)
        num_frames = len(sample_indices)

        times = np.array(frame['data'].times())[sample_indices]
        frame_data = np.zeros((num_frames, self.n))  # array of downsampled data

        if len(self.mask) < len(frame['data']):
            print("Warning!! Channel mask is shorter than the length of the incoming frame")
            print("Skipping frames until we receive the correct mask update....")
            return out

        # Populates the frame_data array
        chans = self.mask[np.arange(len(frame['data']))]
        for rchan, chan  in enumerate(chans):
            # Frame data converted to units of phi0
            if chan < self.fp.num_dets:
                frame_data[:, chan] = frame['data'][f'r{rchan:0>4}'][sample_indices] / 2**16

        # Populates output frames
        for i in range(num_frames):
            fr = core.G3Frame(core.G3FrameType.Scan)
            fr['timestamp'] = times[i]
            fr['data'] = core.G3VectorDouble(frame_data[i, :])
            out.append(fr)

        return out


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument('--src', default='tcp://localhost:4532',
                        help="Address of incoming G3Frames")
    parser.add_argument('--dest', type=int, default=8675,
                        help="Port to server lyrebird frames")
    parser.add_argument('--target-rate', '-t', type=float, default=5)
    parser.add_argument('--layout', '-l', default='grid', choices=['grid', 'wafer'],
                        help="Focal plane layout style")
    parser.add_argument('--xdim', type=int, default=32,
                        help="Number of pixesl in x-dimension for grid layout")
    parser.add_argument('--ydim', type=int, default=32,
                        help="Number of pixesl in y-dimension for grid layout")
    parser.add_argument('--wafer-file', '--wf', '-f', type=str,
                        help="Wafer file to pull detector info from")
    parser.add_argument('--wafer-scale', '--ws', type=float, default=50.,
                        help="scale of wafer coordinates")
    args = parser.parse_args()
    if (args.layout == 'wafer') and (args.wafer_file is None):
        print("Wafer file must be specified to use the wafer layout")
        sys.exit(0)

    smurf_vis = SmurfVis(target_rate=args.target_rate, layout=args.layout, xdim=args.xdim,
                         ydim=args.ydim, wafer_file=args.wafer_file, wafer_scale=args.wafer_scale)
    pipe = core.G3Pipeline()
    pipe.Add(core.G3Reader(args.src))
    pipe.Add(smurf_vis)
    pipe.Add(core.Dump)
    pipe.Add(core.G3NetworkSender, hostname='*', port=args.dest, max_queue_size=1000)
    pipe.Run(profile=True)
