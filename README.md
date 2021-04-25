# PCOT

This is the prototype of the Pancam Operations Toolkit. It's a Python
program with a number of dependencies:

* PyQt
* OpenCV
* numpy
* scikit-image
* pyqtgraph
* matplotlib

A short one-liner script to create an Anaconda environment to run
the program can be found in **createCondaEnv**: it will create an
environment called **pcot**. After installing
Anaconda, run this script. This may take a while!
Then activate the **pcot** environment with **conda activate pcot**.

## Installing

There are a few different methods. All of them require the above Conda environment to be created or
the required packages to be installed directly. If you are using Conda, you need to be running a command
line shell in the Conda environment. In Linux just type * **conda activate pcot** in a terminal window.
In Windows, open the Anaconda Powershell Prompt (installed with Anaconda), run the createCondaEnv script if you haven't already,
then run **conda activate pcot**.

### Install for development

If you are going to be developing PCOT, the simplest thing to do then is go into the PCOT directory and run
**python setup.py develop**. This will install the PCOT package into your Anaconda environment and add the **pcot** script to
run the program. However, the code PCOT uses will still be code inside the directory you downloaded PCOT into.

### Install for execution only

If you are going to be just using PCOT you should install with **python setup.py install** (for now, these instructions may change). 

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
