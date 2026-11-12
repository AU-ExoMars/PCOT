# Spectral parameter files

The *spectral parameter* node applies a named, pre-defined expression - such as a band ratio or a band depth -
to an image. The parameters are organised into **groups**, typically one for each camera or published
set of parameters, and you choose a group and then a parameter in the node's tab.

PCOT comes with some built-in groups, but you can add your own by writing a **spectral parameter file**
and telling PCOT where it is. This page describes how to do that.

## An example

A spectral parameter file is a [YAML](https://yaml.org/) file containing one or more groups.
Here is a complete file with one group of three parameters:

```yaml
My camera:
  date: 12th November 2026
  desc: |
    Example spectral parameters for my camera, from
    Bloggs, J. (2026). Some spectral parameters. Journal of Examples, 1, 1-10.
  parameters:
    R671_438 ferric and dust:
      desc: Ferric minerals and dust
      expr: a$671/a$438
    S438_671 oxidation:
      desc: Related to degree of oxidation
      expr: (a$671-a$438)/(671-438)
    "BD532: ferric":
      desc: Identifies ferric minerals, particularly hematite
      expr: 1-(a$532/((0.53*a$500)+(0.47*a$568)))
```

## The format

At the top level, the file is a dictionary of groups. Each key is the name of a group, as it will appear
in the node, and a file can contain as many groups as you like.

### Groups

Each group must have all three of these items:

| Item | Contents |
|------|----------|
| `date` | The date the group was written. This can be any text; it is there for people reading the file, and PCOT doesn't use it. |
| `desc` | A full description of the group, preferably with a reference to where the parameters come from. Starting the text with a vertical bar, as in the example, lets it run over several lines. |
| `parameters` | A dictionary of the parameters in the group. Each key is the name of a parameter, as it will appear in the node. |

### Parameters

Each parameter must have both of these items:

| Item | Contents |
|------|----------|
| `expr` | The expression which calculates the parameter. |
| `desc` | A longer description of the parameter, and any notes. |

The name of the parameter is all that the node shows when you choose one, so it is a good idea
to put a short description in the name itself, as the built-in parameters do
(for example, "R671_438 ferric and dust").

### Expressions

The expression is written in the same language as the [*expr* node](expr.md), and can use the same
operators and functions - including functions added by plugins. The input image is always the variable `a`,
and there are no other variables.

The bands of the image are usually selected with the `$` operator: `a$671` is the band of `a` with
a centre wavelength of 671nm. A filter name or position can be used instead of a wavelength.
The [tutorial](../gettingstarted/tutorial.md) introduces expressions and this operator.

If the node's input image doesn't have a band the expression needs, the node will show an error.
This means that a group will generally only work with images from the camera it was written for.

### YAML pitfalls

YAML gives some characters special meanings, which can cause surprises:

* A name containing a colon must be put in quotes, like `"BD532: ferric"` in the example.
* An expression must be put in quotes if it contains a colon followed by a space, or a `#` with
a space before it, or if it starts with a character such as `[`, `{`, `*`, `&`, `!` or a quote.
None of the built-in expressions need this.
* Indentation matters, and must be done with spaces, not tabs. All the groups must be indented by
the same amount, and so must all the parameters in a group.

If in doubt, put quotes around the name or expression.

## Telling PCOT about the file

Open the [settings dialog](settings.md) with *Settings* in the *Edit* menu, open the *Locations* section,
and add the file to the list called **locations of user spectral parameters**. You can add as many
files as you like.

The files are read when PCOT starts, so **you will need to restart PCOT** after adding a file to
the list or editing a file which is already in it.

## Rules and errors

* The built-in groups are loaded first, followed by your files in the order they are listed.
* **Two groups can't have the same name.** A file is rejected if it contains a group with the same name as
a built-in group, or as a group in a file earlier in the list - so you can't replace a built-in group, but
you can copy one and give it a different name.
* **A file with an error in it is ignored completely**: none of its groups are loaded, even those
which are correct. An error could be invalid YAML, a missing item, an expression which PCOT can't
understand, or a group name which is already used.
* A file in the list which doesn't exist is skipped.

None of these problems will stop PCOT starting. Instead, PCOT tells you about each one when the main
window opens, and they are also written to the log. Other files in the list are not affected.

## Sharing documents

A PCOT document usually contains everything needed to run it, but a *spectral parameter* node only stores the
**names** of its group and parameter, not the expression. If you send a document which uses one of your
own groups to someone else, they will need your spectral parameter file too, added to their
settings as described above. Without it, the node will show an error saying that there is no such group.

Similarly, if you change an expression in a file, documents which use that parameter will use the
new expression the next time they are run.

## The built-in file

The built-in groups are in a file of exactly the same format,
[`builtin_spectral_parameters.yaml`](https://github.com/AU-ExoMars/PCOT/blob/master/src/pcot/assets/data/builtin_spectral_parameters.yaml),
which is a good source of examples. It contains these groups:

| Group | Source |
|-------|--------|
| AUPE LWAC | Allender et al. (2020), [doi:10.1029/2019EA000692](https://doi.org/10.1029/2019EA000692) |
| AUPE RWAC | Allender et al. (2020), as above |
| PanCam | Coates et al. (2017), The PanCam instrument for the ExoMars rover, Astrobiology 17(6-7), 511-541 |

Please don't edit this file to add your own parameters: it will be replaced when PCOT is updated.
