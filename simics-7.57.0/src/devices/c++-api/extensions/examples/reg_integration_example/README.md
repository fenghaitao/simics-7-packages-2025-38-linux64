# Simics C++ Modeling Extension API Example Register Integration

This is a very simple example that shows how a project would integrate generated Simics C++ registers into their unit.

## Directory Structure
```
reg_integration_example
│   README.md
│   CMakeLists.txt
│   module_load.py
│   regs.cpp
│   regs.h
│   sample_device.cpp
│   sample_device.h
│
└───test
│   │   CMakeLists.txt
│   │   s-info-status.py
│   │   s-simple-test.py
│   │   SUITEINFO
```

<style>
table{
    border-collapse: collapse;
    border-spacing: 0;
    border:2px solid;
}

th{
    border:2px solid;
}

td{
    border:1px solid;
}
</style>

## File Details

| File                  | Description |
| :-------------------: | :------: |
| README.md             | Markdown documentation (this file) |
| CMakeLists.txt        | Example CMake file that builds and runs the example and is suiteable to be used as a starting point for projects |
| module_load.py        | Python file that loads the example into Simics |
| regs.cpp              | The simulated generated register's source file |
| regs.h                | The simulated generated register's header file |
| sample_device.cpp     | The simulated unit using the generated registers, source file |
| sample_device.h       | The simulated unit using the generated registers, header file |
| test                  | The example Simics Python test directory |
| test/CMakeLists.txt   | Example CMake file for running the unit test |
| test/s-info-status.py | Simics status and info file for the unit |
| test/s-simple-test.py | The simple Simics Python test |
| test/SUITEINFO        | SUITEINFO file |

This simple example integrates simulated generated registers (regs.h/.cpp) and integrates them into a sample device (sample_device.h/.cpp) that would mimic what an end user would do in their real project. The simple test just loads the registers within the device and does a simple read/write sequence and verifies the return values.

## Build

This section describes how to build the example.

### Cleanup

To cleanup previous build
```bash
rm -rf linux64/ cmake-build/
```

### Configure

```bash
cmake -S . -B ./cmake-build -G Ninja -DSIMICS_ENABLE_TESTS_FROM_PACKAGES=1 -DCMAKE_BUILD_TYPE=Release -DCMAKE_C_COMPILER=$CC -DCMAKE_CXX_COMPILER=$CXX
```

### Build

```bash
cmake --build ./cmake-build --verbose --target SampleDevice |& tee build.log
```

## Run

This section describes how to run the example

```bash
# This will run all the tests, including the example and unit tests
ctest --test-dir cmake-build --output-on-failure --timeout 10 |& tee run.log
# If you wish to just run the example by itself you can do
# Windows
./simics.bat --batch-mode ./examples/reg_integration_example/test/s-simple-test.py
# Linux
./simics --batch-mode ./examples/reg_integration_example/test/s-simple-test.py
```
