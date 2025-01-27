# TaggedVariantDicts

Sometimes it is necessary to store different kinds of object in a list. We can do this with
TaggedAggregates, provided the objects are all TaggedDicts and there is a field in all the dicts
which tells us which type it is - a "discriminator". 

For example, we can create two dict types:

```python
    tdt1 = TaggedDictType(
        a=("a", int, 10),
        b=("b", str, "foo"),
        c=("c", float, 3.14)
    )
    tdt2 = TaggedDictType(
        a=("a", int, 10),
        b=("b", float, 3.14),
        d=("d", str, "wibble"),
        e=("e", bool, False)
    )
```
and wrap them both in a TaggedVariantDictType:
```python
    tvdt = TaggedVariantDictType("type",
                                 {
                                        "type1": tdt1,
                                        "type2": tdt2
                                    })
```
Here, the discriminator is a field called "type",
and value "type1" tells us it must be of the first type defined above. We don't necessarily need
to define field in the dict types, because the variant wrapper will add it automatically.

We can now create a list of these variants:
```python
    tl = TaggedListType("stuff", tvdt, 0)
    lst = tl.create()
```
create a "type 1" dict:
```python
    d = tdt1.create()
```
create a new variant wrapper and set it to that new dict:
```python
    t = tvdt.create().set(d)
```
and append it to the list:
```python
    lst.append(t)
```
We can pass a type name to the `create` method of the variant type to automatically create
an embedded dict of the correct type, so we could write the above lines as:
```python
d = tvdt.create("type1")
lst.append(d)
```

To examine an item, we can get its discriminator value:
```
    assert lst[0].get_type() == 'type1'
```
and get the item itself with the `get` method in the variant:
```
    assert lst[0].get().a == 10
```
