#pragma once

#include "datastreamer.h"
#include <core/G3Reader.h>

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

};

