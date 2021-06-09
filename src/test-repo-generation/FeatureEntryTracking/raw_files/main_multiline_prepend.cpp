#include <iostream>

bool get_some_arg_value(const char *seed, bool init) {
  size_t i = 0;
  bool res = init;
  while (seed[i]) {
    res = !res;
  }
  return res;
}

int main(int argc, char *argv[]) {
  // roll encryption
  bool encryption = get_some_arg_value(
              "Lorem ipsum dolor sit amet, consetetur sadipscing elitr", true);
  // roll verbosity
  bool verbose = get_some_arg_value(
              "Lorem ipsum dolor sit amet, consetetur sadipscing elitr, sed "
              "diam nonumy eirmod tempor invidunt ut labore et dolore magna", false);
  return 0;
}
