#!/usr/bin/env python

import numpy as np
import socket, curses, json, traceback, math, argparse, math, sys, os, stat
from operator import itemgetter, attrgetter


from configutils.dfmux_config_constructor import get_physical_id, sq_phys_id_to_info
from configutils.dfmux_config_constructor import uniquifyList, generate_dfmux_lyrebird_config


from spt3g import core, dfmux, networkstreamer
from spt3g.core import genericutils as GU
from spt3g import core, dfmux, networkstreamer, auxdata



import warnings
warnings.filterwarnings("ignore")


def make_square_block(n_things):
    sq = n_things**0.5
    if n_things == int(math.floor(sq))**2:
        return (sq,sq)
    else:
        sq = int(math.floor(sq))
        return (sq, sq+1)

def write_get_hk_script(fn, hostname):
    script = '''#!/bin/bash
nc %s 9989
''' % hostname
    print fn
    f = open(fn, 'w')
    f.write(script)
    f.close()
    st = os.stat(fn)
    os.chmod(fn, st.st_mode | stat.S_IXUSR)


class BoloPropertiesFaker(object):
    def __init__(self):
        self.wiring_map = None
        self.bolo_props = None
        self.sent_off = False
        return

    def __call__(self, frame):
        if frame.type == core.G3FrameType.Wiring:
            self.wiring_map = frame['WiringMap']
            return self.send_off(frame)
        elif frame.type == core.G3FrameType.Calibration:
            if 'BolometerProperties' in frame:
                self.bolo_props = frame['BolometerProperties']
            elif 'NominalBolometerProperties' in frame:
                self.bolo_props = frame['NominalBolometerProperties']

    def send_off(self, frame):
        if self.wiring_map != None and self.bolo_props == None:

            #faking the frame data
            self.bolo_props = auxdata.BolometerPropertiesMap()

            n_chans = 0
            squids = {}
            for k in self.wiring_map.keys():
                wm = self.wiring_map[k]
                c = wm.channel + 1

                if c > n_chans:
                    n_chans = c
                sq = get_physical_id(wm.board_serial, 
                                         wm.crate_serial, 
                                         wm.board_slot,
                                         wm.module + 1)
                squids[sq] = 1
            n_squids = len(squids.keys())

            sq_layout = make_square_block(n_squids)
            ch_layout = make_square_block(n_chans)

            sq_x_sep = ch_layout[0] + 1
            sq_y_sep = ch_layout[1] + 1
            ch_x_sep = 1
            ch_y_sep = 1

            for i, sq in enumerate( sorted(squids.keys()) ):
                x = i % sq_layout[0]
                y = i // sq_layout[0]
                squids[sq] = (1.2 * x * ch_layout[0], 1.2* y * ch_layout[1])

            #need nsquids
            #need nbolos per squid
            for k in self.wiring_map.keys():
                wm = self.wiring_map[k]
                sq_id = get_physical_id(wm.board_serial, 
                                            wm.crate_serial, 
                                            wm.board_slot,
                                            wm.module + 1)

                w_id = get_physical_id(wm.board_serial, 
                                           wm.crate_serial, 
                                           wm.board_slot)

                sql = squids[sq_id]
                x = sql[0] + ((wm.channel) % ch_layout[0]) * ch_x_sep
                y = sql[1] + ((wm.channel) // ch_layout[0]) * ch_y_sep

                bp = auxdata.BolometerProperties()
                bp.physical_name = k
                bp.band = 0
                bp.pol_angle = 0
                bp.pol_efficiency = 0
                bp.wafer_id = w_id
                bp.squid_id = sq_id
                bp.x_offset = x
                bp.y_offset = y
                self.bolo_props[k] = bp

            out_frame = core.G3Frame(core.G3FrameType.Calibration)
            out_frame['BolometerProperties'] = self.bolo_props
            return [out_frame, frame]
        else:
            return frame


        
class BirdConfigGenerator(object):
    def __init__(self, 
                 lyrebird_output_file = '',
                 get_hk_script_name= '',
                 hostname = '', hk_hostname = '',
                 port = 3, hk_port = 3
    ):
        self.l_fn = lyrebird_output_file
        self.get_hk_script_name = get_hk_script_name
        self.is_written = False
        self.bolo_props = None
        self.wiring_map = None
        self.hostname = hostname
        self.hk_hostname = hk_hostname
        self.port = port
        self.hk_port = hk_port
    def __call__(self, frame):
        if frame.type == core.G3FrameType.Calibration:
            if 'BolometerProperties' in frame:
                bp_id = 'BolometerProperties'
            elif 'BolometerPropertiesNominal' in frame:
                bp_id = 'BolometerPropertiesNominal'
            else:
                raise RuntimeError("bp fucked")
            self.bolo_props = frame[bp_id]
            self.write_config()
        elif frame.type == core.G3FrameType.Wiring:
            self.wiring_map = frame['WiringMap']
            self.write_config()
    def write_config(self):
        if self.wiring_map == None or self.bolo_props == None:
            return
        config_dic = generate_dfmux_lyrebird_config(
            self.l_fn,
            self.wiring_map, self.bolo_props, 
            hostname = self.hostname,
            hk_hostname = self.hk_hostname,
            port = self.port,
            hk_port = self.hk_port
        )
        write_get_hk_script(self.get_hk_script_name, 
                            self.hostname)
        print("Done writing config file")

class IdSerialMapper(object):
    def __init__(self, wiring_map):
        self.mp = {}
        self.mp_inv = {}
        for k in wiring_map.keys():
            wm = wiring_map[k]
            board_id = get_physical_id(wm.board_serial,
                                       wm.crate_serial,
                                       wm.board_slot)
            self.mp[ wm.board_serial ] = board_id
            self.mp_inv[board_id] = wm.board_serial
    def get_id(self, serial):
        return self.mp[serial]
    def get_serial(self, id):
        return self.mp_inv[id]

###########################
## Squid display portion ##
###########################
def add_timestamp_info(screen, y, x, ts, col_index):
    s = ts.Description()
    screen.addstr(y, x, s[:s.rfind('.')], curses.color_pair(col_index))

#need screen geometry and squid list and squid mapping
def add_squid_info(screen, y, x, 
                   sq_label, sq_label_size,
                   carrier_good, nuller_good, demod_good,
                   temperature_good, 
                   voltage_good,
                   max_size, 
                   bolometer_good, 
                   fir_stage,
                   #routing_good,
                   feedback_on,
                   bolo_label = '',
                   neutral_c = 3, good_c = 2, bad_c = 1):

    col_map = {True: curses.color_pair(good_c), 
               False: curses.color_pair(bad_c) }
    current_index = x
    screen.addstr(y, current_index, sq_label, curses.color_pair(neutral_c))
    current_index += sq_label_size

    screen.addstr(y, current_index, 'C', col_map[carrier_good])
    current_index += 1

    screen.addstr(y, current_index, 'N', col_map[nuller_good])
    current_index += 1

    screen.addstr(y, current_index, 'D', col_map[demod_good])
    current_index += 1

    screen.addstr(y, current_index, 'T', col_map[temperature_good])
    current_index += 1

    screen.addstr(y, current_index, 'V', col_map[voltage_good])
    current_index += 1

    screen.addstr(y, current_index, '%d'%fir_stage, col_map[fir_stage == 6])
    current_index += 1

    #screen.addstr(y, current_index, 'R', col_map[routing_good])
    #current_index += 1

    screen.addstr(y, current_index, 'F', col_map[feedback_on])
    current_index += 1

    if (not bolometer_good):
        screen.addstr(y, 
                      current_index, ' '+bolo_label[:(max_size - 7 - sq_label_size )], 
                      col_map[False])

def load_squid_info_from_hk( screen, y, x, 
                             hk_map,
                             sq_dev_id, sq_label, sq_label_size, 
                             max_size, serial_mapper):
    carrier_good = False
    nuller_good = False 
    demod_good = False
    temp_good = False 
    volt_good = False 
    bolometer_good = False
    full_label = 'NoData'
    fir_stage = 0
    routing_good = False

    feedback_on = False


    board_id, mezz_num, module_num = sq_phys_id_to_info(sq_dev_id)
    board_serial = serial_mapper.get_serial(board_id)

    #code for loading hk info for display
    if hk_map != None and board_serial in hk_map:
        board_info = hk_map[board_serial]
        mezz_info = hk_map[board_serial].mezz[mezz_num]
        module_info = hk_map[board_serial].mezz[mezz_num].modules[module_num]

        
        fir_stage = int(board_info.fir_stage)



        routing_good = module_info.routing_type.lower() == 'routing_nul'
        feedback_on = module_info.squid_feedback.lower() == 'squid_lowpass'

        carrier_good = not module_info.carrier_railed
        nuller_good = not module_info.nuller_railed
        demod_good = not module_info.demod_railed

        def dic_range_check(dr, dv):
            for k in dv.keys():
                assert(k in dr)
                rng = dr[k]
                v = dv[k]
                if v < rng[0] or v > rng[1]:
                    return False
            return True

        voltage_range = {'MOTHERBOARD_RAIL_VCC5V5': (5,6),
                         'MOTHERBOARD_RAIL_VADJ': (2,3),
                         'MOTHERBOARD_RAIL_VCC3V3': (3,3.6),
                         'MOTHERBOARD_RAIL_VCC1V0': (0.8, 1.2),
                         'MOTHERBOARD_RAIL_VCC1V2': (1, 1.5), 
                         'MOTHERBOARD_RAIL_VCC12V0': (11, 13), 
                         'MOTHERBOARD_RAIL_VCC1V8': (1.6, 2), 
                         'MOTHERBOARD_RAIL_VCC1V5': (1.3, 1.7), 
                         'MOTHERBOARD_RAIL_VCC1V0_GTX': (0.7, 1.3)}

        temp_range = {'MOTHERBOARD_TEMPERATURE_FPGA': (0,80), 
                      'MOTHERBOARD_TEMPERATURE_POWER': (0,80),
                      'MOTHERBOARD_TEMPERATURE_ARM': (0,80),
                      'MOTHERBOARD_TEMPERATURE_PHY': (0,80)}
        
        #mezz voltages
        mezz_voltage_range = {'MEZZANINE_RAIL_VCC12V0': (11,13), 
                               'MEZZANINE_RAIL_VADJ': (2,3), 
                               'MEZZANINE_RAIL_VCC3V3': (3,4) }

        temp_good = dic_range_check( temp_range, board_info.temperatures)

        volt_good = ( dic_range_check( voltage_range, board_info.voltages) or
                      dic_range_check( mezz_voltage_range, mezz_info.voltages)
                  )

        bolometer_good = True
        bolo_label = ''


        n_railed = 0
        n_diff_freq = 0
        n_dan_off = 0
        for b in module_info.channels.keys():
            chinfo = module_info.channels[b]
            if (chinfo.dan_railed):
                n_railed += 1
            elif (chinfo.carrier_frequency != chinfo.demod_frequency):
                n_diff_freq += 1
            elif ( (not (chinfo.dan_accumulator_enable and
                         chinfo.dan_feedback_enable and
                         chinfo.dan_streaming_enable ) )
                   and (chinfo.carrier_frequency > 0  and chinfo.carrier_amplitude > 0) ):
                n_dan_off += 1
                      
                
        bolometer_good = not (n_railed or n_diff_freq or n_dan_off)
        
        if not bolometer_good:
            if n_railed:
                full_label = "DanRail:%s"%(n_railed)
            elif n_diff_freq:
                full_label = "CDDiffFreq:%s"%(n_diff_freq)
            elif n_dan_off:
                full_label = "DanOff:%s"%(n_dan_off)
        else:
            full_label = ''



    add_squid_info(screen, y, x, 
                   sq_label, sq_label_size,
                   carrier_good, nuller_good, demod_good,
                   temp_good, volt_good,
                   max_size,
                   bolometer_good, 
                   fir_stage,
                   #routing_good,
                   feedback_on,
                   bolo_label = full_label,
    )

def GetHousekeepingMessenger(frame, hostname):
    print 'gethk', frame.type
    if frame.type == core.G3FrameType.Wiring:
        print 'should be getting hk'
        os.system( "nc %s 9989" % hostname )

class SquidDisplay(object):
    def __init__(self,  
                 squids_per_col = 32, 
                 squid_col_width = 30):
        self.squids_list = None
        self.squids_per_col = squids_per_col
        self.squid_col_width = squid_col_width
        self.serial_mapper = None
        self.str_id_lst = ["       Carrier",
                           "       Nuller",
                           "       Demod",
                           "       Temp",
                           "       Voltage",
                           "    fir#",
                           " squid Feedback"
        ]
        self.highlight_index = [7 for s in self.str_id_lst]
        

    def init_squids(self, squids_list) :
        self.n_squids = len(squids_list) + len(self.str_id_lst) + 1
        self.squids_list = squids_list

        self.sq_label_size = max(map(len, squids_list)) + 3        
        ncols = int(math.ceil(float(self.n_squids)/self.squids_per_col))

        self.screen_size_x = ncols * self.squid_col_width
        self.screen_size_y = self.squids_per_col + 2

        self.pos_map = {}
        #assign an x, y location to each squid

        for j, sq in enumerate(sorted(squids_list, cmp = GU.str_cmp_with_numbers_sorted)):
            i = j + len(self.str_id_lst) + 1
            y =  i % self.squids_per_col + 1
            x = 1 + self.squid_col_width * ( i // self.squids_per_col)
            self.pos_map[sq] = (x,y)

        self.stdscr = curses.initscr()

        y, x = self.stdscr.getmaxyx()
        if y < self.screen_size_y:
            raise RuntimeError("screen is not tall enough, extend to %d", self.screen_size_y)
        if x < self.screen_size_x:
            raise RuntimeError("screen is not wide enough, extend to %d", self.screen_size_x)

        curses.start_color()
            
        # Turn off echoing of keys, and enter cbreak mode,
        # where no buffering is performed on keyboard input
        curses.noecho()
        curses.cbreak()
        curses.curs_set(0)
        
        self.screen = self.stdscr.subwin(0, self.screen_size_x, 0, 0)

        curses.init_pair(1, curses.COLOR_RED,     curses.COLOR_WHITE)
        curses.init_pair(2, curses.COLOR_GREEN,   curses.COLOR_BLACK)
        curses.init_pair(3, curses.COLOR_BLUE,    curses.COLOR_BLACK)
        curses.init_pair(4, curses.COLOR_YELLOW,  curses.COLOR_BLACK)
        curses.init_pair(5, curses.COLOR_BLUE,  curses.COLOR_WHITE)


        self.stdscr.clear()
        self.screen.clear()
        self.screen.refresh()

    def __call__(self, frame):
        if frame.type == core.G3FrameType.Wiring:
            wiring_map = frame['WiringMap']
            squid_ids = []
            for k in wiring_map.keys():
                wm = wiring_map[k]
                squid_ids.append( get_physical_id(wm.board_serial, 
                                                  wm.crate_serial, 
                                                  wm.board_slot,
                                                  wm.module + 1) )
            squid_ids = uniquifyList(squid_ids)
            self.init_squids(squid_ids)
            self.serial_mapper = IdSerialMapper(frame['WiringMap'])

        elif frame.type == core.G3FrameType.Housekeeping:
            if self.squids_list == None:
                return
            #do update
            if frame != None:
                hk_data = frame['DfMuxHousekeeping']
            else:
                hk_data = None
            self.stdscr.clear()
            self.screen.clear()
            #self.screen.box()

            #CNDTV6F
            if hk_data != None:
                add_timestamp_info(self.screen, 0,2, hk_data[hk_data.keys()[0]].timestamp, 5)
                for i, s in enumerate(self.str_id_lst):
                    offset = 4
                    self.screen.addstr(i+1, offset, s, curses.color_pair(2))
                    self.screen.addstr(i+1, offset + self.highlight_index[i], 
                                       s[self.highlight_index[i]], curses.color_pair(3))
                    
                self.screen.hline(len(self.str_id_lst) + 1, 0, 
                                  '-', self.squid_col_width)
                self.screen.vline(0, self.squid_col_width-1, 
                                  '|', len(self.str_id_lst)+1)

            for i, s in enumerate(self.squids_list):
                p = self.pos_map[s]
                load_squid_info_from_hk( self.screen, p[1], p[0], 
                                         hk_data,
                                         s, s, self.sq_label_size, 
                                         self.squid_col_width, self.serial_mapper)
            self.screen.refresh()
        elif frame.type == core.G3FrameType.EndProcessing:
            if self.squids_list != None:
                self.stdscr.keypad(0)
                curses.echo()
                curses.nocbreak()
                curses.endwin() 

if __name__=='__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('hostname')
    parser.add_argument('--port',type=int, default=8675)
    parser.add_argument('--hk_port',type=int, default=8676)
    parser.add_argument('--local_hk_port',type=int, default=8677)
    parser.add_argument('--lyrebird_output_file', default = 'lyrebird_config_file.json')
    parser.add_argument('--get_hk_script', default = 'get_hk.sh')

    args = parser.parse_args()
    #core.set_log_level(core.G3LogLevel.LOG_DEBUG)

    script_path = os.path.dirname(os.path.realpath(__file__))
    script_path = script_path + '/../bin/'

    lyrebird_output_file = script_path + args.lyrebird_output_file
    get_hk_script = script_path + args.get_hk_script

    pipe = core.G3Pipeline()
    pipe.Add(networkstreamer.G3NetworkReceiver, hostname = args.hostname, port = args.hk_port)
    pipe.Add(BoloPropertiesFaker)
    pipe.Add(BirdConfigGenerator, 
             lyrebird_output_file = lyrebird_output_file, 
             hostname = args.hostname, 
             get_hk_script_name = get_hk_script,
             hk_hostname = '127.0.0.1',
             port = args.port, 
             hk_port = args.local_hk_port)

    pipe.Add(GetHousekeepingMessenger, hostname = args.hostname)
    pipe.Add(networkstreamer.G3NetworkSender,
             port = args.local_hk_port,
             maxsize = 10,
             max_connections = 10,
             frame_decimation = {core.G3FrameType.Timepoint: 0}
          )

    pipe.Add(SquidDisplay)
    try:
        pipe.Run()
    finally:
        curses.curs_set(1)
        curses.echo()
        curses.nocbreak()
        curses.endwin()
        traceback.print_exc()  # Print the exception