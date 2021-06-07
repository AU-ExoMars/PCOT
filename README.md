# PCOT

This is the prototype of the Pancam Operations Toolkit. 

## Installing

PCOT is a Python
program (and library) with a number of dependencies:

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
* Install Anaconda and cd to the PCOT directory (which contains this file).
* Run the command **./createCondaEnv**. This will create an environment called **pcot**, and will take some time
* Activate the environment with **conda activate pcot**.
* Install PCOT into the environment with **python setup.py develop** (not 'install'; we want to be able to update easily).
* You should now be able to run **./pcot** to start the application.

### Installing on Windows
* Install Anaconda.
* Open the Anaconda PowerShell Prompt application and change directory to the PCOT directory (which contains this file).
* Run the command **./createCondaEnv.bat**. This will create an environment called **pcot**, and will take some time
* Activate the environment with **conda activate pcot**.
* Install PCOT into the environment with **python setup.py develop** (not 'install'; we want to be able to update easily).
* You should now be able to run **./pcot** to start the application.

## Environment variables

It's a good idea, but not mandatory, to set the environment variable
**PCOTUSER** to a string of the form **name \<email\>**. For example,
in Linux I have added the following to my **.bashrc** file
```
export PCOT_USER="Jim Finnis <jcf12@aber.ac.uk>"
```
This data is added to all saved PCOT graphs. If the environment variable
is not set, the username returned by Python's getpass module is used
(e.g. 'jcf12').
