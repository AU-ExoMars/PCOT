# Common runtime issues

## Can't start Qt on Linux

This sometimes happens:
```txt
qt.qpa.plugin: Could not load the Qt platform plugin "xcb" in "" even though it was found.
This application failed to start because no Qt platform plugin could be initialized. Reinstalling the application may fix this problem.

Available platform plugins are: eglfs, linuxfb, minimal, minimalegl, offscreen, vnc, wayland-egl, wayland, wayland-xcomposite-egl, wayland-xcomposite-glx, webgl, xcb.

```
Try this:
```bash
export QT_DEBUG_PLUGINS=1
pcot
```
to run the program again, and look at the output.
You might see errors like this (I've removed some stuff):
```txt
QFactoryLoader::QFactoryLoader() checking directory path "[...]envs/pcot/bin/platforms" ...
Cannot load library [...]/plugins/platforms/libqxcb.so: (libxcb-xinerama.so.0: cannot open shared object file: No such file or directory)
QLibraryPrivate::loadPlugin failed on "...[stuff removed].. (libxcb-xinerama.so.0: cannot open shared object file: No such file or directory)"
```
If that's the case, install the missing package:
```
sudo apt install libxcb-xinerama0
```
That might help. Otherwise, send a message to us with the output from the ```QT_DEBUG_PLUGINS``` run and we will investigate.

## Conda fails on Windows

I have once seen an error involving OpenSSH not being correctly installed
on Windows when the `conda create...` command was run. This happened toward the end of
the installation.

To fix it, I just ran the command again - it installed OpenSSH correctly
and I was able to proceed.
