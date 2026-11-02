# The configuration system

This page describes how PCOT stores its global configuration, and how
plugins (and other parts of PCOT) can add their own sections to it. For
the user's view of the settings, see [the settings dialog](../userguide/settings.md).

The code lives in `pcot.config`.

## The configuration file

The configuration is stored in `pcot_config.yaml` in the user's home
directory (the path is `pcot.config.CONFIG_PATH`). It is a YAML file
whose top level is a set of named **sections**. Each section belongs to
a **section handler**, which turns the section's YAML data into whatever
Python objects it needs, and back again. PCOT itself has two sections:

| Section | Handler | Contents |
|---|---|---|
| `configuration` | `MainConfigHandler` | the main settings - everything in the settings dialog. Loaded into `pcot.config.data`. |
| `recents` | `RecentsConfigHandler` | the list of recently opened files, read with `pcot.config.getRecents()` |

A file with a plugin section added might look like this (shortened):

```yaml
configuration:
  default_camera: PANCAM
  defaultbayerpattern: RGGB
  locations:
    pcotfiles: /home/jim
    ...
  qt_platform: auto
  sigfigs: 5
edgedetect:
  method: sobel
  threshold: 0.8
recents:
- /home/jim/test.pcot
```

## Section handlers

A section handler is a subclass of `pcot.config.ConfigSectionHandler`.
Its constructor passes the section's name (the top-level YAML key) to the
superclass constructor, and it must implement three methods:

* `load(self, conf)` - called with the section's data from the YAML file,
which will be plain Python data: dicts, lists, strings, numbers, booleans and `None`.
The handler should build its own data from this.
* `save(self)` - returns the section's data as plain Python data which
YAML can write (as above).
* `create(self)` - called instead of `load()` when the section isn't in the
file, either because there is no config file yet or because the section
has been added since the file was last saved. It should create default data.

Exactly one of `load()` and `create()` will be called before `save()`, so `save()`
can always assume the data exists.

Handlers are registered with `pcot.config.addConfigSection(handler)`. The
handler object usually also holds the section's data, so that other code can
get to it through the handler.

## When sections are loaded

The configuration is loaded by `load_config()` when `pcot.config` is first
imported - which happens on `import pcot`, before `pcot.setup()` is called.
It has to happen this early because the configuration says where to find
plugins (`locations.pluginpath`).

This means most sections are registered *after* the file has been read.
That's fine: `addConfigSection()` knows the configuration has already been
loaded, and initialises the new section straight away - calling `load()`
with the section's data if the file has it, or `create()` if it doesn't. So
by the time `addConfigSection()` returns, the handler's data is ready to use,
whenever it is called.

Calling `load_config()` again re-reads the file and reinitialises every
registered section.

## When the configuration is saved

`pcot.config.save()` writes every section to the file. PCOT calls it:

* when the application exits,
* when the user accepts changes in the settings dialog,
* when a default directory is changed (`setDefaultDir()`),
* from the `pcot setconfig` and `pcot config` subcommands.

@@@info
In library and batch use there is no application exit, so nothing is saved
automatically. If your code changes config data and it needs to persist, call
`pcot.config.save()` yourself.
@@@

### Sections with no handler are kept

If the file contains a section which has no registered handler, that section
is written back unchanged when the file is saved. This protects settings
belonging to plugins which have been removed, or which failed to load this
time - they will still be there when the plugin comes back.

### Failed saves don't destroy the file

The new file is written to a temporary file in the same directory, which then
replaces `pcot_config.yaml` only once it has been written completely. If anything
goes wrong - including a handler's `save()` raising an exception - the existing
file is left as it was and the exception is raised from `save()`.

Two side effects of this which are worth knowing about:

* On Linux and macOS, the new file is only readable and writable by its owner,
whatever the file's permissions were before.
* If `pcot_config.yaml` is a symbolic link, it is replaced by an ordinary file.

## Adding a section from a plugin

The easiest way to write a section is to describe its data with a
`TaggedDictType` (see [Node serialisation](nodeser.md) for more on
tagged aggregates). This gives you defaults, type and range checking, and an
editor dialog for free. Here's a section for an edge detection plugin:

```python
import pcot.config
from pcot.config import ConfigSectionHandler, addConfigSection
from pcot.parameters.taggedaggregates import TaggedDictType

# describe the data in the section
EDGE_CONFIG_TYPE = TaggedDictType(
    threshold=("Edge detection threshold", float, 0.5, (0.0, 1.0)),
    method=("Detection method", str, "canny",
            ["canny", "sobel"],
            ["Canny edge detector", "Sobel operator"]),
).setOrdered()


class EdgeConfigHandler(ConfigSectionHandler):
    def __init__(self):
        super().__init__("edgedetect")     # the section name in the YAML file
        self.data = None

    def load(self, conf):
        self.data = EDGE_CONFIG_TYPE.deserialise(conf)

    def save(self):
        # forceUnordered writes a dict rather than a list, so the file is readable
        return self.data.serialise(forceUnordered=True)

    def create(self):
        self.data = EDGE_CONFIG_TYPE.create()


edgeConfig = EdgeConfigHandler()
addConfigSection(edgeConfig)    # loads or creates the data immediately
```

The rest of the plugin then reads and writes settings through the handler:

```python
threshold = edgeConfig.data.threshold
edgeConfig.data.method = "sobel"
pcot.config.save()      # only needed if the change must be saved right now
```

A `TaggedDict` deserialised from a section fills in defaults for any keys
which are missing, so you can add new settings to `EDGE_CONFIG_TYPE` in a later
version of the plugin and existing config files will still load. Keys in the
file which are no longer in the type are silently dropped.

### Choosing a section name

Section names share one namespace, and nothing checks for clashes: if two
handlers use the same name, both are given the same data when it is loaded,
and whichever saves last wins. Use a name based on your plugin's name, and
don't use `configuration` or `recents`.

### Errors

An exception raised by `load()` or `create()` is raised from `addConfigSection()`.
In a plugin, that stops the plugin loading, which stops PCOT starting. If your
section's data might be bad (for example, if the user may have edited the file
by hand), catch the error in `load()`, log it and fall back to `create()`.

### Editing the section

Plugin sections **don't** appear in the settings dialog, or in the `pcot getconfig`
and `pcot setconfig` subcommands, which only handle the main `configuration`
section. If your section is a `TaggedDict`, you can give it its own dialog -
for example, from a menu item (see [Writing PCOT plugins](plugins.md)):

```python
from pcot.ui.taggedaggregates import AggregateEditorDialog

def editEdgeConfig():
    dialog = AggregateEditorDialog(edgeConfig.data)
    dialog.exec()
    if dialog.data():       # None if the user cancelled
        edgeConfig.data = dialog.data()
        pcot.config.save()
```

The dialog edits a copy, which is why the result is put back into the handler.

## The main configuration section

The main section is described by `pcot.config.CONFIG_DICT_TYPE`, a
`TaggedDictType`. Each entry is a tuple:

```python
key=(description, type, default, valid_choices, string_choice_descriptions)
```

The last two are optional:

* `valid_choices` depends on the type:
    * for `str`, a list of the allowed strings - the editor shows a combo box;
    * for `int` and `float`, a `(min, max)` range - the editor shows a spin box;
    * for `Path`, `True` if only directories are allowed, or a file dialog filter string such as `"*.pcot"`.
* `string_choice_descriptions` is only used with a list of string choices. It
is a list of descriptions, one per choice, in the same order. The editor
shows each choice as "choice (description)", and the descriptions are also
included in the autogenerated documentation for parameter files. The value
stored is still the bare choice. If the two lists are different lengths,
creating the `TaggedDictType` raises an error.

For example:

```python
qt_platform=("Qt platform plugin selection on Linux", str, "auto",
             ["auto", "native", "xcb"],
             ["allow PCOT to select", "use Qt's own choice", "Always use XWayland"]),
```

A setting added to `CONFIG_DICT_TYPE` gets its default value when an older
config file is loaded, so no conversion code is needed. If an existing setting's
allowed values change, older files may hold a value which is no longer valid:
`MainConfigHandler.load()` is the place to fix these up before the data is
deserialised (as it does for old Bayer patterns).

The main section's data is `pcot.config.data`. Note that the settings dialog
*replaces* this object when the user accepts changes, so don't keep a reference
to it, or to anything inside it - always go through `pcot.config.data`.
