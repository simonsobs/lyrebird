#include "client.h"

#include <pybindings.h>
#include <container_pybindings.h>

#include <boost/python.hpp>
#include <boost/python/numpy.hpp>

#include <iostream>

namespace np = boost::python::numpy;

template <class A> void PixelConfig::serialize(A &ar, unsigned v)
{
    using namespace cereal;
    // v is the version code!
    
    ar & make_nvp("G3FrameObject", base_class<G3FrameObject>(this));
    ar & make_nvp("name", name);
    ar & make_nvp("x", x);
}

std::string PixelConfig::Description() const
{
    std::ostringstream s;
    s << "PixelConfig(" << x << ", " << y << ")";
    return s.str();
}

std::string PixelConfig::Summary() const
{
    return Description();
}


template <class A> void PixelConfigFrame::serialize(A &ar, unsigned v)
{
    using namespace cereal;
    // v is the version code!
    
    ar & make_nvp("G3FrameObject", base_class<G3FrameObject>(this));
    ar & make_nvp("pixels", pixels);
    ar & make_nvp("equation_labels", equation_labels);
}

std::string PixelConfigFrame::Description() const
{
    std::ostringstream s;
    s << "PixelConfigFrame(" << pixels.size() << " elements)";
    return s.str();
}

std::string PixelConfigFrame::Summary() const
{
    return Description();
}

G3_SERIALIZABLE_CODE(PixelConfig);
G3_SERIALIZABLE_CODE(PixelConfigFrame);


namespace bp = boost::python;

PYBINDINGS("pyrebird")
{
    EXPORT_FRAMEOBJECT(PixelConfig, init<>(),
                       "Description of a channel visual element.")
        .def_readwrite("name", &PixelConfig::name,
                       "Channel name.")
        .def_readwrite("x", &PixelConfig::x,
                       "x position.")
        .def_readwrite("y", &PixelConfig::y,
                       "y position.")
        .def_readwrite("rot", &PixelConfig::rot,
                       "rotation, in degrees.")
        .def_readwrite("vis_template", &PixelConfig::vis_template,
                       "Name of vis_el template to use.")
        .def_readwrite("vis_cmap", &PixelConfig::vis_cmap,
                       "Name of colormap to use.")
        .def_readwrite("equations", &PixelConfig::equations,
                       "Vector of equation strings.");
    EXPORT_FRAMEOBJECT(PixelConfigFrame, init<>(),
                       "Data block for irregularly sampled data.")
        .def_readwrite("pixels", &PixelConfigFrame::pixels,
                       "Vector of PixelConfig objects.")
        .def_readwrite("equation_labels", &PixelConfigFrame::equation_labels,
                       "Short equation labels (for GUI).");
}

BOOST_PYTHON_MODULE(pyrebird) {
    np::initialize();
    G3ModuleRegistrator::CallRegistrarsFor("pyrebird");
}
