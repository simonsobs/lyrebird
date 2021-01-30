#pragma once

#include "datastreamer.h"
#include <core/G3Reader.h>
#include <core/G3TimeStamp.h>

// SDFrameStream - helper class that caches frames and helps manage
// their gradual release to the visualizer.

class SDFrameStream {
public:
  std::deque<G3FramePtr> frame_queue;
  void push(G3FramePtr f);
  G3FramePtr pop();

  double get_display_delay();
  double get_lag_s();
  double get_display_time(G3FramePtr f);

private:
  pthread_mutex_t mutex_ = PTHREAD_MUTEX_INITIALIZER;

  // Trigger initialization of vis_offset on first frame.
  int reinit = 1;

  // The frame will be released for display at frame["timestamp"] +
  // vis_offset.  Don't assume this is positive.
  double vis_offset = 0;

  // For correcting when voluntary latency is to high...
  double mon_lag;   // worst case since mon_time0.
  double mon_time0; // timestamp.
};


// SDStreamer - self-describing streaming TOD.
//
// The relevant config info looks like this:
// {
//  "network_streamer_hostname": "host",
//  "network_streamer_port": 8675,
// }

class SDStreamer :public DataStreamer {
public:
  SDStreamer(Json::Value streamer_json_desc,
             std::string tag, DataVals * dv, int us_update_time
             );
  ~SDStreamer(){}
  int get_num_elements();

  int configure_datavals(std::vector<equation_desc> &eq_descs,
                         std::vector<vis_elem_repr> &vis_elems,
                         std::map<std::string, vis_elem_repr> &vis_templates);

  G3FramePtr get_frame();
  SDFrameStream frame_stream;

protected:
  void initialize();
  void update_values(int v);
  void uninitialize();
 
private:
  double val;
  std::vector<int> s_path_inds;
  std::vector<std::string> chan_names;
  Json::Value streamer_json_desc_;
  std::string reader_str;
  std::string hostname_;
  int port_;
  int streamer_type_;
  G3ReaderPtr frame_grabbing_function_;

  //Additional thread for timed release of data.
  pthread_t reader_thread;
};
