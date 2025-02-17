# Regions of interest and tagged aggregates

@@@alert
Hopefully you will never need to know about the hackery involved in the complex tagged
aggregate serialisation involved in regions of interest, but if you do...
@@@

ROIs are a bit complicated. All ROIs have a set of attributes in common, and each subtype has
some extra. To do that, we have code like this:

```python
BASEROIFIELDS = [
    ("type", ("type", str, "")),
    ("label", ("label", Maybe(str), "")),
    ("labeltop", ("label on top?", bool, False)),
    ("colour", ("colour", ROICOLOURTYPE)),
    ("thickness", ("thickness", Number, 0)),
    ("fontsize", ("fontsize", Number, 10)),
    ("drawbg", ("draw background", bool, True)),
    ("drawBox", ("draw box", bool, True)),
    ("drawEdge", ("draw edge", bool, True)),
]

# ...

class ROIRect(ROI):
    """Rectangular ROI"""
    tpname = "rect"
    # build the tagged dict structure we use for serialising rects - it's a tagged dict with the fields
    # of a rect, plus the base ROI fields.
    TAGGEDDICTDEFINITION = BASEROIFIELDS + [
        ('bb', ('rectangle', rectType)),
        ('isset', ('is rectangle set? (internal)', bool, False))]

    TAGGEDDICT = TaggedDictType(*TAGGEDDICTDEFINITION)
```
so that `ROIRect.TAGGEDDICT` is a type definition for all the fields we need. We then have methods
in each ROI:

* `to_tagged_dict(self)` will convert the ROI to the right kind of tagged dict
* `from_tagged_dict(self,td)` will set the current ROI from its tagged dict

The CTAS methods for `XFormRect` (the rectangle node) are then:
```
    def serialise(self, node):
        # this returns None, but stores data into .params ready for serialisation
        # Again - more hackery to get around ROI having 'type' and this clashing with node's 'type'
        node.params = TaggedDict(self.params)  # build a dict without the 'type' (see init)
        # Serialise the ROI into a TaggedDict, and copy fields from that into the node.params we just made.
        rser = node.roi.to_tagged_dict()
        for k in node.params.keys():
            node.params[k] = rser[k]
        # don't return anything; our return is essentially the
        # node.params
        return None

    def nodeDataFromParams(self, node):
        node.roi.from_tagged_dict(node.params)
```

Finally `ROI.new_from_tagged_dict(td)` will create an ROI from a tagged dict; it will inspect the
type field to see what type is. 

## How `multidot` does CTAS of ROIs

The *multidot* node uses this system in quite a complex way, because it needs to be able to store
a list of different ROIs. It does this using a list of variant dicts - here are the type definitions:

```python
class XFormMultidot(XFormType):
    # ...
    
    TAGGEDVDICT = TaggedVariantDictType("type",
                                        {
                                            "painted": ROIPainted.TAGGEDDICT,
                                            "circle": ROICircle.TAGGEDDICT
                                        })

    TAGGEDLIST = TaggedListType(TAGGEDVDICT, 0)
```
Here is the `serialise` method:
```python
def serialise(self, node):
    # create the list of ROI data
    lst = self.TAGGEDLIST.create()
    for r in node.rois:
        # for each ROI, convert to a TaggedDict
        d = r.to_tagged_dict()
        # wrap it in a TaggedVariantDict and store it in the list
        dv = self.TAGGEDVDICT.create().set(d)
        lst.append(dv)

    node.params = TaggedDict(self.params)
    node.params.rois = lst
    # and don't return anything, because we've stored the data in node.params.
    return None
```
and here is the `nodeDataFromParams` method:
```python
    def nodeDataFromParams(self, node):
        """CTAS deserialisation"""
        lst = node.params.rois

        rs = []
        for x in lst:
            d = x.get()
            roi = ROI.new_from_tagged_dict(d)
            rs.append(roi)

        # filter out any zero-radius circles
        node.rois = [r for r in rs if isinstance(r, ROIPainted) or r.r > 0]
```




