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
        if(frame->type == G3Frame::PipelineInfo)
            continue;
        sds->frame_stream.push(frame);
    }
}

int SDStreamer::configure_datavals(
        std::vector<equation_desc> &eq_descs,
        std::vector<vis_elem_repr> &vis_elems,
        std::map<std::string, vis_elem_repr> &vis_templates)
{
    cout << "Blocking to load config from stream..." << endl;
    int retries = 5;
    for (int retries = 5; retries > 0; retries--) {
        G3FramePtr frame = get_frame();
        if(frame->type != G3Frame::Wiring)
            continue;

        // Check for config data?
        if (!frame->Has("equations"))
            continue;

        cout << "config frame received, probably." << endl;
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
        return chan_names.size();
    }
    log_error("Failed to decode a config frame.");

    return 0;
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
    double frame_t = double(*f->Get<G3Time>("timestamp")) / G3Units::s;
    double now = double(G3Time::Now()) / G3Units::s;

    // Monitor the latency in case it can be improved.
    if (reinit) {
        // State machine reset... make a measurement.
        vis_offset = now - frame_t;
        mon_lag = 1000.;
        mon_time0 = now;
        reinit = 0;
    } else {
        // If frames aren't coming in fast enough, increase the deliberate latency.
        double t = get_display_time(f);
        if (t - now < 0.1)
            vis_offset += (now - t) * .9;
        // If our current latency seems too large, adjust.
        mon_lag = std::min(t - now, mon_lag);
        if (now - mon_time0 > 5.) {
            // Worst case not that bad?
            if (mon_lag > 0.1)
                vis_offset -= mon_lag*.9;
            // Reset.
            mon_lag = 1000;
            mon_time0 = now;
        }
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
    }
    pthread_mutex_unlock(&mutex_);
    return f;
}

/**
 * Returns the time (double) at which frame f should be displayed.
 * Frame better have a timestamp entry!
 */

double SDFrameStream::get_display_time(G3FramePtr f) {
    auto t = double(*f->Get<G3Time>("timestamp")) / G3Units::s;
    return t + vis_offset;
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
    // Inspect next frame.
    double t = 0;
    pthread_mutex_lock(&mutex_);
    if (!frame_queue.empty()) {
        auto f = frame_queue.back();
        t = get_display_time(f);//double(*f->Get<G3Time>("timestamp")) / G3Units::s;
    }
    pthread_mutex_unlock(&mutex_);

    if (t == 0)
        return 1000;
    return t - double(G3Time::Now()) / G3Units::s;
}

/**
 * Returns the latency parameter (offset between visualization stream
 * and frame stream), in seconds.  Positive for causal relationships.
 */
double SDFrameStream::get_lag_s()
{
    return vis_offset;
}
