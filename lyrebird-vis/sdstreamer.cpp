#include "sdstreamer.h"
#include <iostream>

#include <G3Frame.h>
#include <G3Pipeline.h>
#include <G3Map.h>
#include <G3Vector.h>

using namespace std;

SDStreamer::SDStreamer(Json::Value desc,
                       std::string tag, DataVals * dv, int us_update_time ) :
    DataStreamer(tag, dv, us_update_time, DSRT_STREAMING),
    reader_str(std::string("tcp://") +
               desc["network_streamer_hostname"].asString() +
               ":" + desc["network_streamer_port"].asString()),
    frame_grabbing_function_(new G3Reader(reader_str))
{
    hostname_ = desc["network_streamer_hostname"].asString();
    port_ = desc["network_streamer_port"].asInt();
    streamer_type_ = desc["streamer_type"].asInt();

    log_debug("streamer type %d", streamer_type_);
}

void SDStreamer::initialize() {
    std::cout<<"Init SDStreamer"<<std::endl;
    for (auto n: chan_names)
        s_path_inds.push_back(data_vals->add_data_val(n, 0, true, 0));
}

void SDStreamer::uninitialize() {
    std::cout<<"Uninit SDStreamer"<<std::endl;
}

static
G3FramePtr get_frame(G3ReaderPtr & fun, std::string reader_str){

	std::deque<G3FramePtr> out;
	fun->Process(G3FramePtr(NULL), out);
	
	if (out.size() == 0){
		log_error("Lyrebird lost connection");
		sleep(1);
		try {
			fun = G3ReaderPtr(new G3Reader(reader_str));
		} catch (const std::exception&) {}
	}
	
	return out.front();
}

int SDStreamer::configure_datavals(
        std::vector<equation_desc> &eq_descs,
        std::vector<vis_elem_repr> &vis_elems,
        std::map<std::string, vis_elem_repr> &vis_templates)
{
    cout << "Blocking to load config from stream..." << endl;
    G3FramePtr frame = get_frame(frame_grabbing_function_, reader_str);
    
    if(frame->type == G3Frame::Scan) {
        // Check for config data?
        if (!frame->Has("equations"))
            return 0;
        cout << "config frame received." << endl;
        // Load visual elements.
        G3VectorDoubleConstPtr x = frame->Get<G3VectorDouble>("x");
        G3VectorDoubleConstPtr y = frame->Get<G3VectorDouble>("y");
        G3VectorDoubleConstPtr r = frame->Get<G3VectorDouble>("rotation");
        G3VectorStringConstPtr t = frame->Get<G3VectorString>("templates");
        G3VectorStringConstPtr e = frame->Get<G3VectorString>("equations");
        G3VectorStringConstPtr c = frame->Get<G3VectorString>("cmaps");
        G3VectorStringConstPtr n = frame->Get<G3VectorString>("cname");
        for (int i=0; i<(int)x->size(); i++) {
            chan_names.push_back(n->at(i));
            string eq_name = n->at(i) + "_equation";
            vis_elem_repr v = vis_templates[t->at(i)];
            v.x_center = x->at(i);
            v.y_center = y->at(i);
            v.rotation = r->at(i);
            v.labels.push_back("vi_" + n->at(i));
            v.equations.push_back(eq_name);
            vis_elems.push_back(v);
            equation_desc eqd;
            eqd.eq = e->at(i);
            eqd.cmap_id = c->at(i);
            eqd.label = eq_name;
            eqd.display_label = "OneTrueEq";
            eqd.sample_rate_id = n->at(i);
            eqd.display_in_info_bar = true;
            eqd.color_is_dynamic = false;
            eq_descs.push_back(eqd);
            v.labels.push_back("label_" + n->at(i));
        }
    }
    return chan_names.size();
}

void SDStreamer::update_values(int ind) {

    G3FramePtr frame = get_frame(frame_grabbing_function_, reader_str);

    // We only expect to find data in Scan frames.
    if (frame->type == G3Frame::Scan){
        G3VectorDoubleConstPtr z = frame->Get<G3VectorDouble>("data");
        for (int i=0; i<(int)z->size() && i < get_num_elements();  i++)
            data_vals->update_val(s_path_inds[i], z->at(i));
    } else if (frame->type == G3Frame::EndProcessing) {
        for (int i=0; i<get_num_elements(); i++)
            data_vals->update_val(s_path_inds[i], 0.);
        log_error("Lost connection to server ep");
    }
}

int SDStreamer::get_num_elements(){
    return chan_names.size();
}
