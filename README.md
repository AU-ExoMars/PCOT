# PCOT

This is the prototype of the Pancam Operations Toolkit. 

## Installing with Anaconda
PCOT is a Python program (and library) with a number of dependencies:

* Python >3.8
* PyQt
* OpenCV
* numpy
* scikit-image
* pyperclip
* matplotlib

I find the best way to manage these is to use Anaconda. Installation has been tested on Windows 10
and Ubuntu 20.04. The first thing you'll need to do is install Anaconda, which can be done from here:
* Windows: https://docs.anaconda.com/anaconda/install/linux/
* Linux: https://docs.anaconda.com/anaconda/install/linux/
* MacOS: https://docs.anaconda.com/anaconda/install/mac-os/ (untested)


### Obtain the software

For both Windows and Ubuntu this is the obvious first step. This can be done by
either downloading the archive from Github and extracting it into a new directory,
or cloning the repository. In both cases, the top level directory should be called
PCOT (this isn't really mandatory but makes the instructions below simpler).
The best way to download is this:

* Make sure you have a Github account and membership of the AU-ExoMars group.
* Open an Anaconda shell window (see below)  
* If you have an SSH key set up for GitHub, type this command into the shell:
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
* **Windows:** Open the **Anaconda PowerShell Prompt** application, which will have been installed when you
installed Anaconda.
* **Linux and MacOS**: just open a Bash shell  


### Installing on Ubuntu / MacOS
Assuming you have successfully installed Anaconda and cloned or downloaded PCOT as above:
* Open a bash shell
* **cd** to the PCOT directory (which contains this file).
* Run the command **./createCondaEnv**. This will create an environment called **pcot**, and will take some time.
* Activate the environment with **conda activate pcot**.
* Install PCOT into the environment with **python setup.py develop** (not 'install'; we want to be able to update easily).
* You should now be able to run **pcot** to start the application.

### Installing on Windows
Assuming you have successfully installed Anaconda and cloned or downloaded PCOT as above:
* Open the Anaconda PowerShell Prompt application from the Start Menu.
* **cd** to the PCOT directory (which contains this file).
* Run the command **./createCondaEnv.bat**. This will create an environment called **pcot**, and will take some time.
* Activate the environment with **conda activate pcot**.
* Install PCOT into the environment with **python setup.py develop** (not 'install'; we want to be able to update easily).
* You should now be able to run **pcot** to start the application.

## Installing without an environment manager
* Directly install the packages at the top of this
file using **pip3 *packagename packagename* ...**
* Install PCOT with **python setup.py develop** as above
* You should now be able to run **pcot** to start the application.
  
The danger here, of course, is that the new packages may clash with your existing 
python environment.

## Running PCOT
Open an Anaconda shell and run the following commands (assuming you installed PCOT into your home directory):
```shell
cd PCOT
conda activate pcot
pcot
```

## Running PCOT inside Pycharm
These instructions apply to Anaconda installations.

* First set up the Conda environment and interpreter:
    * Open PyCharm and open the PCOT directory as an existing project.
    * Open **Settings..** (Ctrl+Alt+S)
    * Select **Project:PCOT / Python Interpreter**
    * Select the cogwheel to the right of the Python Interpreter dropdown and then select  **Add**.
    * Select **Conda Environment**.
    * Select **Existing Environment**.
    * Select the environment: it should be something like **anaconda3/envs/pcot/bin/python**.
    * Select **OK**.
* Now set up the run configuration:
    * Select **Edit Configurations** from the configurations drop down in the menu bar
    * Add a new configuration (the + symbol)
    * Set **Script Path** to **PCOT/src/pcot/__main__.py**
    * Make sure the interpreter is something like **Project Default (Python 3.8 (pcot))**, i.e. the Python interpreter of the pcot environment.
* You should now be able to run and debug PCOT.

## Environment variables

It's a good idea, but not mandatory, to set the environment variable
**PCOTUSER** to a string of the form **name \<email\>**. For example,
in Linux I have added the following to my **.bashrc** file:
```
export PCOT_USER="Jim Finnis <jcf12@aber.ac.uk>"
```
This data is added to all saved PCOT graphs. If the environment variable
is not set, the username returned by Python's getpass module is used
(e.g. 'jcf12').
