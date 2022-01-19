---
date: 2022-01-19
title: Notes on importing PDS4
summary: some notes on the PDS4 input method and ramifications for sources
---

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
