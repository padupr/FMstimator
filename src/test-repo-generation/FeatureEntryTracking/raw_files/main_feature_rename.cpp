#include <iostream>

// todo more functions

int main(int argc, char *argv[]) {
  bool encryption = false;
  bool compression = true;
  // implication
  bool logging = true;
  bool verbose_output = false;
  if (verbose_output && !logging) {
    std::cout << "verbose_output implies logging" << std::endl;
    exit(1);
  }
  // mandatory mutually exclusive
  bool mux_1 = false;
  bool mux_2 = false;
  bool mux_3 = true;
  if (mux_1 + mux_2 + mux_3 != 1) {
    std::cout << "Exactly one mux config must be enabled" << std::endl;
    exit(1);
  }
  // todo logging
}
