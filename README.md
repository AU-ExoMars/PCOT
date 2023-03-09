# PCOT

This is an early version of the Pancam Operations Toolkit. This is
a Python application and library primarily intended for 
processing data from the Pancam
instrument on the Rosalind Franklin rover, although it lends itself
to any task involving processing multispectral image data.

For example, with PCOT you can:
* load ENVI (BSQ interleaved 4-byte float) and (to a basic level) PDS4 multispectral images
* load multiple images in other formats (e.g. PNG) and combine them into
multispectral images
* define regions of interest in the data
* perform mathematical operations
* view spectra and histograms

and many other things besides. PCOT is highly extensible and open-source,
so any missing functionality is easily added.

PCOT operates on a graph model - the data is processed through a set of nodes
which manipulate it in various ways (e.g. add regions of interest, perform
maths, splice images together, merge image channels, plot spectra). A PCOT
document describes this graph, and we
intend that documents are distributed along with the data they generate
to help reproducibility.

More documentation can be found [here](https://au-exomars.github.io/PCOT/)

## Installation

PCOT is a Python program (and library) with a number of dependencies,
notably numpy and PySide2 (the official Python interface to Qt).
We find the best way to manage these is to use
[Anaconda](https://anaconda.com/)
and
[Poetry](https://python-poetry.org/).
Installation has been tested on Windows 10,
MacOS and Ubuntu 20.04.

### Install Anaconda
The first thing you will need to do is install Anaconda, which can be done from here:

* Windows: https://docs.anaconda.com/anaconda/install/windows/
* Linux: https://docs.anaconda.com/anaconda/install/linux/
* MacOS: https://docs.anaconda.com/anaconda/install/mac-os/ (untested)

### Obtain the software

This can be done by
either downloading the archive from Github and extracting it into a new
directory,
or cloning the repository. In both cases, the top level directory should be
called
PCOT (this isn't really mandatory but makes the instructions below simpler).
The best way to download is this:

* Open an Anaconda shell window (see below)  
* If you have an SSH key set up for GitHub, type this command into the shell
(**changing the repository address if it is different**):
```shell
git clone git@github.com:AU-ExoMars/PCOT.git
```
* Otherwise type this:
```shell
git clone https://github.com/AU-ExoMars/PCOT.git
```
* You should now have a PCOT directory which will contain this file (as README.md)
and quite a few others.

#### Opening Anaconda's shell on different OSs
* **Windows:** Open the **Anaconda Powershell Prompt** application, which will have been installed when you
installed Anaconda. This can be found in the Start menu under Anaconda3,
or in the applications list in Anaconda Navigator (which is also in the Start
menu in the same place).
* **Linux and MacOS**: just open a Bash shell  

### Installing on Ubuntu / MacOS
Assuming you have successfully installed Anaconda and cloned or downloaded
PCOT as above:

* Open a bash shell
* **cd** to the PCOT directory (which contains this file).
* Run the command **conda create -n pcot python=3.8 poetry=1.1.6**.
This will create an environment called **pcot** which uses Python 3.8 and
the Poetry dependency and packaging manager. It may take some time.
* Activate the environment with **conda activate pcot**.
* Now run **poetry install**. This will set up all the packages PCOT is
dependent on and install PCOT.
* You should now be able to run **pcot** to start the application.

### Installing on Windows
Assuming you have successfully installed Anaconda and cloned or downloaded PCOT as above:

* Open the Anaconda PowerShell Prompt application from the Start Menu.
* **cd** to the PCOT directory (which contains this file).
* Run the command **conda create -n pcot python=3.8 poetry**.
This will create an environment called **pcot** which uses Python 3.8 and the Poetry dependency
and packaging manager. It may take some time.
* Activate the environment with **conda activate pcot**.
* Now run **poetry install**. This will set up all the packages PCOT is dependent on and install
PCOT.
* You should now be able to run **pcot** to start the application.


## Running PCOT
Open an Anaconda shell and run the following commands (assuming you installed PCOT into your home directory):
```shell
cd PCOT
conda activate pcot
pcot
```

### Create an 'executable' icon (MacOS)
Note: these instructions were created and tested under MacOS but should be usable on other systems
with some adaptation.

The above commands can be put into a bash script which will allow PCOT to be run by clicking on an icon.

 Open a text editor (e.g. TextEdit, Notepad++, Sublime, etc) and create a new file called **pcot.sh**, and save it
 to your desktop (or wherever you want the icon). Add the following to this file:
```shell
#!/usr/bin/env bash
eval "$(conda shell.bash hook)"
conda activate pcot
pcot
```
Open a terminal window and navigate to the location of your new script, then run the following command to give it
permission to run:
```shell
chmod +x pcot
```

You can now use the icon to run PCOT.

Note: you may need to set up your system to open ```.sh``` files with Terminal by default.

## Running PCOT inside Pycharm
These instructions apply to Anaconda installations.

* First set up the Conda environment and interpreter:
    * Open PyCharm and open the PCOT directory as an existing project.
    * Open **File/Settings..** (Ctrl+Alt+S)
    * Select **Project:PCOT / Python Interpreter**
    * If the Python Interpreter is not already Python 3.8 with something like **anaconda3/envs/pcot/bin/python**
        * Select the cogwheel to the right of the Python Interpreter dropdown and then select  **Add**.
        * Select **Conda Environment**.
        * Select **Existing Environment**.
        * Select the environment: it should be something like **anaconda3/envs/pcot/bin/python**.
        * Select **OK**.
* Now set up the run configuration:
    * Select **Edit Configurations...** (or it might be **Add Configuration...**) from the configurations drop down in the menu bar
    * Add a new configuration (the + symbol) and select **Python**
    * Set **Script Path** to **PCOT/src/pcot/\_\_main\_\_.py**
    * Make sure the interpreter is something like **Project Default (Python 3.8 (pcot))**, i.e. the Python interpreter of the pcot environment.
* You should now be able to run and debug PCOT.

## Environment variables

It's a good idea, but not mandatory, to set the environment variable
**PCOTUSER** to a string of the form ```name <email>```. For example,
in Linux I have added the following to my **.bashrc** file:
```
export PCOT_USER="Jim Finnis <jcf12@aber.ac.uk>"
```
This data is added to all saved PCOT graphs. If the environment variable
is not set, the username returned by Python's getpass module is used
(e.g. 'jcf12').

## Common runtime issues

### Can't start Qt on Linux

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
That should help. Otherwise, send a message to us with the output from the ```QT_DEBUG_PLUGINS``` run and we will investigate.
