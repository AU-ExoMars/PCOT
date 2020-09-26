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
environment called **dev**. After installing
Anaconda, run this script. This may take a while!
Then activate the **dev** environment with **conda activate dev**.


## Environment variables

It's a good idea, but not mandatory, to set the environment variable
**PCOTUSER** to a string of the form **name <email>**. For example,
in Linux I have added the following to my **.bashrc** file
```
export PCOT_USER="Jim Finnis <jcf12@aber.ac.uk>"
```
This data is added to all saved PCOT graphs. If the environment variable
is not set, the username returned by Python's getpass module is used
(e.g. 'jcf12').
