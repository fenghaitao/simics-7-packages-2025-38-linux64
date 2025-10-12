# Sample device with an external library

**NOTE**: Depending on and shipping external shared libraries is a potential
point of failure. If multiple modules require the same shared library in
different versions or if end-users do manual changes to the library search
paths, modules depending on shared libraries could pick up wrong libraries
and the resulting errors can be very hard to analyze. We strongly recommend
statically linking against third party code. Only if a shared library is your
only option you should use it.

This sample device illustrates how modules can be built with external
dependencies (libraries) in such a way that they can later be distributed
as part of a Simics package.

## Scenario

Assume there is a Simics-external library `libexternal_lib.<suffix>` where
suffix would be either `dll` or `so`, depending on the host OS.
The library is somewhere on your development host together with the
associated header files used to build code that uses the library.

You want to create a DML device model that uses a function offered by the library,
and when you are done, you want to ship the device model to other users.
Now you do not know if they have the library installed and even if they do,
you do not know where, or even worse they could have installed an incompatible
version of the library. Thus, every user of your device would need to do some
manual preparation like setting library search paths or similar things when 
starting Simics. 

To avoid that, you can place the library file into the directory `[host]/sys/lib`
of a package and Simics will find it at runtime, without the need to set
up library search paths.  `[host]` is either `win64` or `linux64` depending on 
the host type you are running Simics on.

In this example, the external library is initially located in a sub-directory 
of the module (at `modules/sample-device-with-external-lib/technically/arbitrary/path/on/disk`), 
but technically it could be anywhere on your disk.  The 
example Makefile shows how the library is used for linking with your device
and then the Makefile moves the library into `[host]/sys/lib` of your project such 
that it can be found by the Simics core at runtime. You can change the computation 
performed by the sample library to really see that it is called. 

After building, you could then use `project-packager` to wrap the module
you created - together with the library in `[host]/sys/lib` - into a Simics package
that other users can add to their Simics setup, and your device would
also find the library in the installed package. 

## Building and running the example

First, create a Simics project. When this is done, import the sample device into your project.  If you can read this, you have likely already done that.  

* On Linux: `bin/project-setup --copy-device=sample-device-with-external-lib`

* On Windows: `bin\project-setup.bat --copy-device=sample-device-with-external-lib`

Now you can invoke `make` (on Linux) or `bin\make.bat` (on Windows) and the module will be built.

The interesting part is in the module Makefile (`modules/sample-device-with-external-lib/Makefile`).
First, take a look at the very end. There is a rule to build the external library. We have that
because the library is a synthetic one. A real library would be pre-built and no build rule
for the library would exists in your module makefile.

The other important rules are all documented in the makefile itself. You can see there how
to compile and link with the external library and you can also find a rule that does the copy
of the library into its runtime location *inside* of the project.

### Windows host note
On Windows, libraries in `win64\sys\lib` are only found in packages.
Hence, in order to use the device from your project on Windows you first need to build it,
then package it using `bin\project-packager.bat`, then install it to some directory
using `ispm` and then associate the installed package with your project using
`bin\addon-manager.bat`.

### Testing the device
You can play with the device after building it by starting an empty Simics session and then doing:

```
@SIM_create_object('sample_device_with_external_lib', 'sample')
output-radix 16
write-device-reg register = sample.bank.regs.trigger data = 0x1234567890ABCDEF
read-device-reg register = sample.bank.regs.trigger
```

If you get an error like this on Windows when doing the testing:
```
*** Error loading module sample-device-with-external-lib: Failed to load module 'sample-device-with-external-lib' ('...\win64\lib\sample-device-with-external-lib.dll'): "[Error 126] The specified module could not be found."
```

It means that Simics could not find the external library, most likely because
(on Windows) you forgot to add the package that contains it to the project's package list.
See above in `Windows host note`.
