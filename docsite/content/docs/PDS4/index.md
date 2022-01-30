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

## Persistence is hard

The proctools system can only read in a whole bunch of labels *en masse*.
And you can only read data from a label. However, I'm reading the labels
into a primitive - but serialisable - PDS4Product object. Except these
objects being serialisable isn't a great win when I can't read data from them!

One possibility - every time we deserialise the data read the directory
again and make explicit links from PDS4Product to underlying data. Ugh?

## Sequences of actions
In these notes, I typically mean a proctools "product" when I refer
to a "label"; I have my own internal product type (PDS4Product) and it
would get confusing if I did otherwise.

### Scan button

* **loadLabelsFromDirectory(clear=False)**
    * preserves existing PDS4Product *products* array and *selected* array
    * loads labels (THIS IS SLOW, but labels are not serialisable)
    * generates a LID to label map
    * generates serialisable PDS4Product data from labels which don't have one yet
    in the object's *products* array
    * deletes PDS4Product data which don't have labels with that LID (i.e. files were deleted since last scan)
* **populateTableAndTimeline** does what it says, preserving *selected* array

### Read button

* **loadData** 
    * ensures that all items are the same type and if that type is not 'image'
    that only one is selected
    * **buildImageFromProducts** 
        * may call **loadLabelsFromDirectory** if there isn't a lidToLabel entry for a product's LID
        * gets the labels for the products from lidToLabel
        * glues them together into an image
    * runs the graph
* **updateDisplay** calls canvas.display on the image
        
### Serialisation

* **PDS4Input.serialise**
    * **PDS4Product.serialise**
        * converts to dict
        * converts non-serialisable items to serialisable (e.g. filter)
    * serialises canvas
    
        
## Deserialisation

* **PDS4Input.deserialise**
    * **PDS4Product.deserialise*
        * converts serialisable to non-serialisable (e.g. finds filter)
        * passes dict to product constructor as kwargs
    * clears LID to label map
    * clears output
    
Input will be blank because the LID to label map will be empty; no
labels will have been loaded.


## Appendix: data in PDS4 product from proctools

Here's the kind of thing that comes out of PDS4:

|Key|Value|
|-----|-----|
|lid|urn:esa:psa:emrsp_rm_pan:data_partially_processed:pan_par_sc_l03_spec-rad_20210921t101327.048z||
|start|2021-09-21T10:13:27.0484Z|
|stop|2021-09-21T10:13:28.7444Z|
|type|spec-rad|
|acq_desc|To acquire a sequence of stereo and colour WAC images with right Red filter and left RGB filters.|
|acq_id|2|
|acq_name|PANCAM_WAC_RRGB|
|camera|WACL|
|exposure_duration|1.696|
|filter|3|
|filter_num|3|
|filter_bw|120|
|filter_cwl|440|
|filter_id|C03L|
|filter_name|Broadband Blue|
|model|FM|
|rmc_ptu|15.0|
|seq_img_num|4|
|seq_num|6|
|sol_id|5|
|sub_instrument|WACL|
|subframe_y|1|
|subframe_x|1|
