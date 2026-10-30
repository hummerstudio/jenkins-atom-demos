#include <cassert>
#include <stdexcept>

#include "calc.h"

int main() {
    assert(add(2, 3) == 5);
    assert(divide_int(9, 3) == 3);
    bool threw = false;
    try {
        divide_int(1, 0);
    } catch (const std::invalid_argument&) {
        threw = true;
    }
    assert(threw);
    return 0;
}
