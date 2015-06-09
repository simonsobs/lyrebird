#include "datavals.h"
#include <assert.h>
#include "genericutils.h"
#include "equation.h"
using namespace std;


DataVals::DataVals(int n_vals, int buffer_size){
  //vals = new float[n_vals];
  buffer_size_ = buffer_size;
  buffer_size_full_ = buffer_size_ + 1;


  ring_indices_ = new int[n_vals];
  ring_buffers_ = new float[n_vals * (buffer_size_full_)];
  is_buffered_ = new int[n_vals];

  n_current_ = 0;
  for (int i=0; i < n_vals; i++){
    //vals[i] = 0;
    ring_buffers_[ i * buffer_size_full_] = 0;
    ring_indices_[i] = 0;
    is_buffered_[i] = 0;
  }
  //create read write lock
  if( pthread_rwlock_init( &rwlock_, NULL)) print_and_exit("rwlock_ init failed");
  is_paused_ = false;
}

DataVals::~DataVals(){
  //delete [] vals;
  delete [] ring_indices_;
  delete [] ring_buffers_;
  delete [] is_buffered_;

}

int DataVals::get_ind(std::string id){
  if (id_mapping_.find(id) == id_mapping_.end())
    return -1;
  else
    return id_mapping_[id];
}

int DataVals::add_data_val(std::string id, float val, int is_buffered){
  int index = n_current_;
  if ( id_mapping_.find(id) != id_mapping_.end()  )
    print_and_exit( id + " already in DataVals when adding" );
  for (int j=0; j < buffer_size_full_; j++) ring_buffers_[j+index*buffer_size_full_] = val;
  n_current_++;
  id_mapping_[id] = index;
  is_buffered_[index] = is_buffered;
  return index;
}


void DataVals::update_val(int index, float val){
  if (is_paused_) return;

  //grab read lock
  pthread_rwlock_rdlock (&rwlock_);
  //vals[index] = val;
  ring_buffers_[buffer_size_full_ * index] = val;
  if (is_buffered_[index]){
    ring_buffers_[buffer_size_full_ * index +  ring_indices_[index] + 1] = val;
    ring_indices_[index]++;
    ring_indices_[index] = ring_indices_[index] % buffer_size_;
  }
  pthread_rwlock_unlock (&rwlock_);
}


float * DataVals::get_addr(int index){
  if (index < 0 || index >= n_current_){
    print_and_exit("attempting to get non existent index from DataVals");
  }
  return ring_buffers_ + buffer_size_full_ * index;
}



/**
struct PPToken{
  pp_func func;
  int arg_num;
  float val;
  float * val_addr;
  int dv_index;
};
float evaluate_tokenized_equation_or_die(PPStack<PPToken> * token_stack){
  PPStack<float> eval_stack;
  eval_stack.size = 0;
  for (int i = token_stack->size-1; i >= 0; i--){
    token_stack->items[i].func(&eval_stack, 
			       token_stack->items[i].val_addr == NULL ? &(token_stack->items[i].val) : token_stack->items[i].val_addr, 
			       0 );
  }
  return eval_stack.items[0];
}
 **/


void DataVals::apply_bulk_func(PPStack<PPToken> * token_stack, float * vals){
  PPStack<float> eval_stack;
  pthread_rwlock_wrlock(&rwlock_ );
  for (int j = 0; j < buffer_size_; j++){
    eval_stack.size = 0;
    //does the pp calculation
    for (int i = token_stack->size-1; i >= 0; i--){
      token_stack->items[i].func(&eval_stack, 
				 token_stack->items[i].val_addr == NULL ? &(token_stack->items[i].val) : token_stack->items[i].val_addr, //value to plug in
				 ((ring_indices_[token_stack->items[i].dv_index] + j)%buffer_size_) + 1 );//offset
    }
    //stores the value
    vals[j] = eval_stack.items[0];
  }
  pthread_rwlock_unlock(&rwlock_);
}


void DataVals::toggle_pause(){
  is_paused_ = !is_paused_;
}

int DataVals::get_buffer_size(){
  return buffer_size_;
}

int DataVals::is_buffered(int index){
  return is_buffered_[index];
}