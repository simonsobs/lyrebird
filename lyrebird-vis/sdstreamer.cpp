#include "sdstreamer.h"
#include <iostream>
#include <sys/time.h>

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
    has_lag = true;
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

G3FramePtr SDStreamer::get_frame() {
    //G3ReaderPtr & fun, std::string reader_str){

    std::deque<G3FramePtr> out;
    frame_grabbing_function_->Process(G3FramePtr(NULL), out);
	
    if (out.size() == 0){
        log_error("Lyrebird lost connection");
        sleep(1);
        try {
            frame_grabbing_function_ = G3ReaderPtr(new G3Reader(reader_str));
        } catch (const std::exception&) {}
    }
	
    return out.front();
}

static
void *reader_thread_func(void *ds) {
    auto sds = (SDStreamer*)ds;
    while (true) {
        G3FramePtr frame = sds->get_frame();
        sds->frame_stream.push(frame);
    }
}

int SDStreamer::configure_datavals(
        std::vector<equation_desc> &eq_descs,
        std::vector<vis_elem_repr> &vis_elems,
        std::map<std::string, vis_elem_repr> &vis_templates)
{
    cout << "Blocking to load config from stream..." << endl;
    G3FramePtr frame = get_frame();
    
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
        if (pthread_create( &reader_thread, NULL, reader_thread_func, (void*)this)){
            log_fatal("Could not spawn reader_thread.");
        }
    }
    return chan_names.size();
}

void SDStreamer::update_values(int ind)
{
    // Is it time to display a frame?
    double sleep_time = frame_stream.get_display_delay();
    if (sleep_time > 1e-3)
        return;
    if (sleep_time > 1e-6)
        usleep(int(sleep_time * 1e6));

    G3FramePtr frame = frame_stream.pop();
    if (frame == nullptr)
        return;

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

    // Update latency param.
    lag_s = frame_stream.get_lag_s();
}

int SDStreamer::get_num_elements(){
    return chan_names.size();
}


/** SDFrameStream
 *
 * The SDFrameStream handles the buffering of frames and the timing of
 * their release to the visualizer.  This is threaded; access to
 * frame_queue is protected by frame_mutex.
 */

/**
 * Push a frame into the queue front.  The frame timestamp is examined
 * and compared to the projected display time -- this is used to set
 * the right lag parameter so the display stream is smooth.
 */
void SDFrameStream::push(G3FramePtr f) {
    pthread_mutex_lock(&mutex_);
    frame_queue.push_front(f);
    // Update the timelines.
    G3Time t = *f->Get<G3Time>("timestamp");
    // cout << "Frame " << t << " recd at " << G3Time::Now() << endl;
    // cout << "  current offset is " <<
    //     double(vis_offset - source_offset) / G3Units::s << endl;
    if (next_frame_index == -1) {
        next_frame_index = 0;
        source_offset = t;
        vis_offset = G3Time::Now();
    } else if (source_period < 0) {
        source_period = double(t - source_offset) / G3Units::s;
        vis_period = source_period;
        cout << "Setting source_period and vis_period to: " << source_period << endl;
    } else {
        // When will this frame be displayed, and how does that
        // compare to now?
        double delta = double(
            get_display_time(next_frame_index + frame_queue.size() - 1)
            - G3Time::Now()) / G3Units::s;
        if (delta < lag_thresh) {
            // This will be a noticeably late delivery.  Schedule a
            // slowdown... or make sure the extant one is sufficient.
            if (frame_queue.size() * lag_step > delta) {
                // Recompute it.
                n_lag = frame_queue.size();
                lag_step = delta / n_lag;
                cout << "Adding latency -- " << n_lag << " x "
                     << lag_step << " secs." << endl;
            }
        }
    }
    if (n_lag > 0) {
        vis_offset -= long(lag_step*G3Units::s);
        n_lag--;
    }
    pthread_mutex_unlock(&mutex_);
}

/**
 * Pop a frame from the queue back, if one is available, and return
 * it.  Otherwise return nullptr.
 */
G3FramePtr SDFrameStream::pop() {
    G3FramePtr f = nullptr;
    pthread_mutex_lock(&mutex_);
    if (!frame_queue.empty()) {
        f = frame_queue.back();
        frame_queue.pop_back();
        next_frame_index++;
    }
    pthread_mutex_unlock(&mutex_);
    return f;
}

/**
 * Returns the time at which frame frame_index would be displayed, in
 * the current model.  Only valid if vis_offset and vis_period have
 * been properly defined.
 */

G3Time SDFrameStream::get_display_time(int frame_index)
{
    return vis_offset + long(frame_index * vis_period * G3Units::s);
}

/**
 * Returns the amount of time, in seconds, to wait before showing the
 * next frame.  If this information cannot be computed, some absurdly
 * large number (such as 1000) is returned.  The code that passes
 * frames to the visualizer should call time_to_next_show() and then
 * decides whether to serve the frame, busy wait first, sleep a little
 * first, or go do something else and come back later.
 */
double SDFrameStream::get_display_delay()
{
    if (next_frame_index < 0) {
        // No data yet.
        return 1000;
    }
    if (next_frame_index == 0) {
        // Sure, display it.
        return 0.;
    }
    return double(get_display_time(next_frame_index) - G3Time::Now()) /
        G3Units::s;
}

/**
 * Returns the latency parameter (offset between visualization stream
 * and frame stream), in seconds.  Positive for causal relationships.
 */
double SDFrameStream::get_lag_s()
{
    return double(vis_offset - source_offset) / G3Units::s;
}
