#!/bin/env python

USAGE="""
SDDataSource demo tool.

Invoke as
    ./sd_demo.py config

Then run lyrebird:
    ./lyrebird sd_demo.json

Then start the data stream:
    ./sd_demo.py stream

"""

import optparse as o
o = o.OptionParser(usage=USAGE)
o.add_option('--config-file', default='sd_demo.json')
o.add_option('--num-pix', type=int, default=1024)
opts, args = o.parse_args()

assert(args[0] in ['config', 'stream'])

if args[0] == 'stream':

    from spt3g import core
    import numpy as np
    import time

    counter = 0
    cache = []
    N_CACHE = 4  # For bundled release, set to > 1.
    def pacer(frame):
        global counter, cache
        counter += 1
        if counter == -10:
            time.sleep(10)
        time.sleep(.1)
        cache.append(frame)
        frame = []
        if counter % N_CACHE == 0:
            output = [c for c in cache]
            cache = []
            return output
        return frame

    N_CHROIC = 2
    N_POL = 2
    N_COLOC = N_CHROIC * N_POL
    n = opts.num_pix * N_COLOC
    idx = np.arange(n)
    pi, di = idx // N_COLOC, idx % N_COLOC   #pixel index, coloc index.
    x = np.array(pi % 32) * 1.
    y = np.array(pi // 32) * 1.
    ci, ri = di//2, di%2  # color idx, rot idx
    rot = (((pi % 32 % 2)^(pi // 32 % 2)) + 2*ri) * np.pi/4

    cname = ['test_%04i' % i for i in idx]
    equations = ['/ + 1 s %s 2' % _c for _c in cname]
    cmaps = [["red_cmap","bolo_blue_cmap"][_ci] for _ci in ci]

    tplates = ['template_c%i_p0' % _ci for _ci in ci]

    data = np.zeros(n)

    def gen(frame):
        global counter, data
        out = core.G3Frame()
        out.type = core.G3FrameType.Scan  # is this allowed?
        if counter == 0:
            # Load up the data description.
            out['x'] = core.G3VectorDouble(x)
            out['y'] = core.G3VectorDouble(y)
            out['rotation'] = core.G3VectorDouble(rot)
            out['cname'] = core.G3VectorString(cname)
            out['equations'] = core.G3VectorString(equations)
            out['cmaps'] = core.G3VectorString(cmaps)
            out['templates'] = core.G3VectorString(tplates)
        else:
            data = np.random.normal(size=len(data))
            out['data'] = core.G3VectorDouble(data)
            out['timestamp'] = core.G3Time(time.time() * core.G3Units.seconds)
            out['freq_hz'] = 1.
        return out

    pipe = core.G3Pipeline()
    pipe.Add(gen)
    pipe.Add(core.Dump)
    pipe.Add(pacer)
    pipe.Add(core.G3NetworkSender, hostname='localhost', port=8675, max_queue_size=1000)
    pipe.Run(profile=True)

if args[0] == 'config':

    from configutils import config_constructor as cc

    config_dic = {}
    cc.addGeneralSettings(config_dic, win_x_size=800, win_y_size=600, 
                          sub_sampling=4, max_framerate=-1, max_num_plotted=10000,
                          eq_names = ["osc", "lin"],
                          dv_buffer_size = 1024
    )

    scale_factor = 0.008

    color_maps = ['bolo_cyan_cmap', 'bolo_green_cmap','bolo_blue_cmap','white_cmap']

    cc.addDataVal(config_dic, "speed_tuner", 1., False)
    cc.addGlobalEquation(config_dic, cc.getEquation(
        "a speed_tuner",  "red_cmap", "GlobalEqLabel", "GlobalEquation", "speed_tuner"));

    svg_folder = '../svgs/'

    tplates = []
    for pol in range(4):
        for col in range(2):
            svg1 = svg_folder + 'polpair%i.svg' % col
            svg2 = svg_folder + 'polpair%ih.svg' % col
            tplates.append({
                "name": "template_c%i_p%i" % (col, pol),
                "group": "Detector_type_%i" % col,
                "layer": 1,
                "svg_path": svg1,
                "svg_id": cc.convert_svg_path_to_id(svg1),
                "highlight_svg_path": svg2,
                "highlight_svg_id": cc.convert_svg_path_to_id(svg2),
                "x_scale": 0.008,
                "y_scale": 0.008,
                "rotation": 3.1416 / 4 * pol
            })

    config_dic['visual_element_templates'] = tplates
    config_dic["displayed_global_equations"] = [] #["dummyEqLabel_test_0", "dummyEqLabel_test_6"]
    config_dic["modifiable_data_vals"] = ["speed_tuner"]
    config_dic['external_commands_list'] = ['echo hello', 'echo goodbye']
    config_dic['external_commands_id_list'] = ['SAY HALLO', "SAY GOODBYE"]

    cc.addDataSource(config_dic, "sd_streamer", "sd_streamer", {
        'network_streamer_hostname': '*',
        'network_streamer_port': 8675,
        })
    cc.storeConfigFile(config_dic, opts.config_file)
