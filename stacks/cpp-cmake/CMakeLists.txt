cmake_minimum_required(VERSION 3.20)
project(calc CXX)
set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

add_library(calc src/calc.cpp)
target_include_directories(calc PUBLIC include)
add_executable(calc_run src/main.cpp)
target_link_libraries(calc_run PRIVATE calc)

enable_testing()
add_executable(calc_test tests/test_calc.cpp)
target_link_libraries(calc_test PRIVATE calc)
add_test(NAME calc_test COMMAND calc_test)
