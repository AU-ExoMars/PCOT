# Example plugins

This directory contains some example plugins. To use them, add the path of the directory to the colon-separated 
pluginpath variable in your **.pcot.ini** file, which should be automatically created in your home directory
when you first run PCOT. For example, you could have the following:
```ini
[Locations]
pluginpath = ~/pcotplugins:~/PCOT/pcotplugins
```
In this case, plugins in the **pcotplugins** directory will be loaded, followed by plugins in the
**PCOT/pcotplugins** directory. Both directories are relative to your home directory. Also, all
subdirectories of all the plugin directories will be traversed recursively (this may cause problems
if a plugin requires some packages!)

## Example 1