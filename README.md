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
and Ubuntu 20.04

### Installing on Ubuntu

* Open a bash shell.
* Install Anaconda: https://docs.anaconda.com/anaconda/install/linux/
* cd to the PCOT directory (which contains this file).
* Run the command **./createCondaEnv**. This will create an environment called **pcot**, and will take some time.
* Activate the environment with **conda activate pcot**.
* Install PCOT into the environment with **python setup.py develop** (not 'install'; we want to be able to update easily).
* You should now be able to run **pcot** to start the application.

### Installing on Windows
* Install Anaconda: https://docs.anaconda.com/anaconda/install/windows/
* Open the Anaconda PowerShell Prompt application from the Start Menu.
* cd to the PCOT directory (which contains this file).
* Run the command **./createCondaEnv.bat**. This will create an environment called **pcot**, and will take some time.
* Activate the environment with **conda activate pcot**.
* Install PCOT into the environment with **python setup.py develop** (not 'install'; we want to be able to update easily).
* You should now be able to run **pcot** to start the application.

## Installing without an environment manager
* Directly install the packages at the top of this
file using **pip3 *packagename packagename* ...**
* Install PCOT with **python setup.py develop** as above
* You should now be able to run **pcot** to start the application.
  
The danger here is, of course, clashes with your existing 
python environment.

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
