import argparse
import numpy as np
from spt3g import core
import yaml
import ast

class SmurfVis:
    def __init__(self, target_rate=3, npix=1024, nchroic=2, npol=2):

        self.target_rate = target_rate

        # Generate configuration frame
        ncoloc = nchroic * npol  # number of colocated detectors?
        n =  npix * ncoloc  # Total number of detectors
        idx = np.arange(n)
        pi, di = idx // ncoloc, idx % ncoloc   #pixel index, coloc index.
        x = np.array(pi % 32, dtype=np.float)
        y = np.array(pi // 32) * 1.
        y += y//4 * 0.25  # adds a gap between bands
        ci, ri = di//2, di%2  # color idx, rot idx
        rot = (((pi % 32 % 2)^(pi // 32 % 2)) + 2*ri) * np.pi/4
        cname = ['test_%04i' % i for i in idx]
        equations = ['/ + 1 s %s 2' % _c for _c in cname]
        cmaps = [["red_cmap","bolo_blue_cmap"][_ci] for _ci in ci]
        tplates = ['template_c%i_p0' % _ci for _ci in ci]

        self.cfg_frame = core.G3Frame(core.G3FrameType.Wiring)
        self.cfg_frame['x'] = core.G3VectorDouble(x)
        self.cfg_frame['y'] = core.G3VectorDouble(y)
        self.cfg_frame['rotation'] = core.G3VectorDouble(rot)
        self.cfg_frame['cname'] = core.G3VectorString(cname)
        self.cfg_frame['equations'] = core.G3VectorString(equations)
        self.cfg_frame['cmaps'] = core.G3VectorString(cmaps)
        self.cfg_frame['templates'] = core.G3VectorString(tplates)
        self.sent_cfg = False

        self.n = n
        # Map from rchan to smurf chan (det chan?)
        self.mask = np.arange(n)  # rchan -> smurf channel mask

    def __call__(self, frame):
        out = []
        if not self.sent_cfg:
            out.append(self.cfg_frame)
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
            return

        # Populates the frame_data array
        chans = self.mask[np.arange(len(frame['data']))]
        for rchan, chan  in enumerate(chans):
            # Frame data converted to units of phi0
            frame_data[:, chan] = frame['data'][f'r{rchan:0>4}'][sample_indices] / 2**16

        # Populates output frames
        for i in range(num_frames):
            fr = core.G3Frame(core.G3FrameType.Scan)
            fr['timestamp'] = times[i]
            fr['data'] = core.G3VectorDouble(frame_data[i, :])
            out.append(fr)

        return out


def main():
    smurf_vis = SmurfVis(target_rate=3)
    pipe = core.G3Pipeline()
    pipe.Add(core.G3Reader("tcp://localhost:4532"))
    pipe.Add(smurf_vis)
    pipe.Add(core.Dump)
    pipe.Add(core.G3NetworkSender, hostname='*', port=8675, max_queue_size=1000)
    pipe.Run(profile=True)


if __name__ == '__main__':
    main()
