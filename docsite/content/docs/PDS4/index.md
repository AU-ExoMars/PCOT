---
date: 2022-01-19
title: Notes on importing PDS4
summary: some notes on the PDS4 input method and ramifications for sources
---

# PDS4 input - user experience

* User opens the dialog shown in the figure.
When opened, the directory field (1) should show the last
directory selected (if it still exists) and the table (2) and 
timeline (3) should show
the PDS4 labels that it showed last time. See "persistence" below.
* User selects a directory, and whether that directory should be read
recursively (5).
* User clicks Load Directory (5) button to read this directory recursively or not
* Table and timeline are reloaded. Any labels which were selected prior
to reload are reselected.
* User selects labels in the timeline or table (**ugh**) - selection
in one must be reflected in the other
* User clicks Read Data (6) and if the data is OK (i.e. all image data,
or all HK) it is loaded into the canvas and the output is set.
* **Read Data must turn red when selection changes, like the Replot button
in certain nodes which use matplotlib**

{{< figure src="dialog.png" title="The PDS4 input dialog (proposed)">}}
1. directory
2. table of loaded PDS4 products
3. canvas showing currently selected image (note: may need a way of showing HK
data too)
4. timeline of loaded PDS4 products
5. recursive checkbox and directory load button
6. Read Data button will load the selected data and output it
  

## Persistence
* directory name and recursive state
* contents of table and timeline - i.e. list of all labels found previously
and their files.
* selection state of the above
* actual output data **(should do this for all inputs)**

# Tech. details

This will naturally be the primary input method, and has several steps.

* First, the PDS4 input method code will scan the directory given and create
a set of objects representing PDS4 labels found.
    * This will be done firstly using my own code, then **proctools** when
      it is released.
    * The resulting **PDS4Label** objects will then be used to create
      linear set entities for the browser. I need to modify LinearSetEntity
      so that the **x** field is actually a **getX()** method, so I can
      avoid duplicating data in the linked label object.
    * There will be different kinds of entity for different kinds of
      data (image/HK).

# PDS4Label
      
These objects are created by the directory scanner as it reads labels - no
actual data is read. They give a date, a name, some type info, and some
extra info about the filter if it's an image. All the label should be there,
really, imported as directly as possible.

* Each LinearSetEntity links to this.

* Each Source links to this!

## PDS4Label, Sources and *Sink*

This is going to be a big change to sources: all sources should link
to a PDS4Label if there is one! That also means we'll need to modify the
source viewer in *sink* to show part of the label, and **change it to
some kind of expandable tree view** so we can see details.

## Reading data

Once the user has selected some data, the caller will get each entity
and through that each PDS4 label. Each label will be asked to read
its data. This will typically produce an ImageCube, or it might be some HK
data. Each channel will get a Source with a link to the label as mentioned
above.


