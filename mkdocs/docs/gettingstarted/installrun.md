# Installing and running PCOT


PCOT is available in two forms: a standalone executable and
a source distribution. While the standalone version is much easier to install, it's
harder to use as a library and to modify. It's also quite a large file.

## Standalone version
The standalone executables are available on request from the Aberystwyth team. Once you
have the appropriate executable for your operating system, just run it to run PCOT. No
installation is necessary.

## Installing from source
PCOT is a Python program (and library) with a number of dependencies, including

* Python >3.8
* PyQt
* OpenCV
* numpy
* scikit-image
* pyperclip (may also require other packages in Linux e.g. xsel)
* matplotlib

### Install Anaconda
We find the best way to manage these is to use
[Anaconda](https://anaconda.com/)
and
[Poetry](https://python-poetry.org/).
Installation has been tested on Windows 10,
MacOS and Ubuntu 20.04.
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
* Run the command **conda create -n pcot python=3.8 poetry**.
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

<!--- No longer necessary now that everything is in Pypi.
## One last step
Because the **pds4-tools** package isn't in any Anaconda reposities yet,
you'll need to install it manually. With the pcot environment active, run
```
pip3 install pds4-tools
```
-->

## Running PCOT from source
Open an Anaconda shell and run the following commands (assuming you installed PCOT into your home directory):
```shell
conda activate pcot
pcot
```
If you have installed the binary version you don't need to activate a conda environment.

## Running PCOT inside Pycharm
These instructions apply to source installations.

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
**PCOT_USER** to a string of the form ```name <email>```. For example,
in Linux I have added the following to my **.bashrc** file:
```
export PCOT_USER="Jim Finnis <jcf12@aber.ac.uk>"
```
This data is added to all saved PCOT graphs. If the environment variable
is not set, the username returned by Python's getpass module is used
(e.g. 'jcf12').

## In case of problems
There are a few things which can stop PCOT running - see [issues](issues.md).
