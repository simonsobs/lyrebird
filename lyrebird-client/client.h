#pragma once

#include <G3Frame.h>
#include <G3Map.h>

#include <stdint.h>

using namespace std;

class PixelConfig : public G3FrameObject {
public:
    PixelConfig() {};

    string name;
    float x;
    float y;
    float rot;
    string vis_template;
    string vis_cmap;
    vector<string> equations;

    string Description() const;
    string Summary() const;

    template <class A> void serialize(A &ar, unsigned v);
};    

class PixelConfigFrame : public G3FrameObject {
public:
    PixelConfigFrame() {};

    vector<PixelConfig> pixels;
    vector<string> equation_labels;

    string Description() const;
    string Summary() const;
    template <class A> void serialize(A &ar, unsigned v);
};


G3_SERIALIZABLE(PixelConfig, 0);
G3_SERIALIZABLE(PixelConfigFrame, 0);
