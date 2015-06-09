#pragma once
#include <string>
#include <vector>
#include <unordered_map>
#include <memory>

#include <AntTweakBar.h>
#include <glm/glm.hpp>

#include "simplerender.h"
#include "datavals.h"
#include "equation.h"

struct vis_elem_repr{
  float x_center;
  float y_center;
  float x_scale;
  float y_scale;
  float rotation;
  int layer;

  std::string svg_path;
  std::string highlight_svg_path;

  std::string geo_id;
  std::string highlight_geo_id;

  std::vector<std::string> labels;

  std::vector< equation_desc > equations;
  std::string group;

  std::vector< std::string > labelled_data;
  std::vector< std::string > labelled_data_vs;
};

typedef struct vis_elem_repr vis_elem_repr;


class VisElem{
  /**
     Represents a visual element.


     I've kind of made a sketchy choice, so if you change any of the labelled data,
     labels, or equations you need to call updateAIPointers

   **/

 public:
  VisElem(SimpleRen * simple_ren, 
	  DataVals * dvs,
	  vis_elem_repr v
	  );
  
  void set_drawn();
  void set_not_drawn();

  void set_highlighted(glm::vec3 col);
  void set_not_highlighted();
  
  void update_color();
  
  void update_all_equations();

  glm::mat4 get_ms_transform();//ms = model space
  std::string get_geo_id();

  int get_layer();
  Equation & get_current_equation();

  void animate_highlight(float tstep);

  void set_eq_ind(int ind);


  void get_all_info(std::vector<std::string> &labels, std::vector<std::string> & tags,
		    std::vector<std::string> & tag_vals,
		    std::vector<std::string> & eq_labels,std::vector<float*> & eq_addrs
		    );

  bool string_matches_labels(const char * pattern);

 private:
  //VisElem( const VisElem& );
  const VisElem& operator=( const VisElem& );

  int has_eq;
  int sr_index;
  int highlight_index;
  int layer;
  std::string geo_id;
  SimpleRen * s_ren;
  float hXScale, hYScale, hTDelt;
  std::vector<Equation> equations;

  int eq_ind;

  std::string group;
  std::vector< std::string > labels;

  std::vector< std::string > l_data_labels; //labelled data things
  std::vector< std::string > l_data_vals;
  
};


typedef std::shared_ptr<VisElem> VisElemPtr;