# fmt

Simics C++ API use the [FMT](https://github.com/fmtlib/fmt) library for logging.
Example:

```C++
SIM_LOG_INFO_STR(4, bank_obj_ref(), Register_Read,
                 fmt::format("Partial read from register {}:"
                             " bytes {}-{} -> {:#x}", name(),
                             start_bit_offset / 8,
                             end_bit_offset / 8 - 1, ret));
```

Since only a subset of the FMT library is used, only a subset has been submitted to the Simics Base repo.

The current version is 10.2.1.

The FMT library has been patched to pass Coverity scanning. The diff can be found in the coverity.patch file.
