# Bit conversion

Some images (e.g. PNG) are in 8-bit [0,255] formats which need to be converted
to and from the internal PCOT format, which is 32-bit float in the closed
range [0,1].

## Method 1

### To convert float [0,1] to ubyte [0,255]
We use
```python
a = (b*256).clip(max=255).astype(np.ubyte)
```
This gives the following end points:
```
>>> a=np.linspace(0,0.1,100)
>>> (a*256).clip(max=255).astype(np.ubyte)
array([ 0,  0,  0,  0,  1,  1,  1,  1,  2,  2,  2,  2,  3,  3,  3,  3,  4,
        4,  4,  4,  5,  5,  5,  5,  6,  6,  6,  6,  7,  7,  7,  8,  8,  8,
        8,  9,  9,  9,  9, 10, 10, 10, 10, 11, 11, 11, 11, 12, 12, 12, 12,
       13, 13, 13, 13, 14, 14, 14, 14, 15, 15, 15, 16, 16, 16, 16, 17, 17,
       17, 17, 18, 18, 18, 18, 19, 19, 19, 19, 20, 20, 20, 20, 21, 21, 21,
       21, 22, 22, 22, 23, 23, 23, 23, 24, 24, 24, 24, 25, 25, 25],
      dtype=uint8)

>>> a=np.linspace(0.9,1,100)
>>> (a*256).clip(max=255).astype(np.ubyte)
array([230, 230, 230, 231, 231, 231, 231, 232, 232, 232, 232, 233, 233,
       233, 234, 234, 234, 234, 235, 235, 235, 235, 236, 236, 236, 236,
       237, 237, 237, 237, 238, 238, 238, 238, 239, 239, 239, 239, 240,
       240, 240, 241, 241, 241, 241, 242, 242, 242, 242, 243, 243, 243,
       243, 244, 244, 244, 244, 245, 245, 245, 245, 246, 246, 246, 246,
       247, 247, 247, 247, 248, 248, 248, 249, 249, 249, 249, 250, 250,
       250, 250, 251, 251, 251, 251, 252, 252, 252, 252, 253, 253, 253,
       253, 254, 254, 254, 254, 255, 255, 255, 255], dtype=uint8)

>>> 
```
In other words, the byte values are distributed evenly across the range,
but the pixel value indicates the floor of the value multiplied up (look
at the first four values, they are all zero).

### Converting [0,255] to [0,1]

To convert the other way, which we do more often, it's probably a
good idea to just divide by 255!

## Method 2

### To convert float [0,1] to ubyte [0,255]

```python
a = np.rint(b/255)
```
Given 1000 values in [0,1] as before, we get
```
array([  0.,   0.,   1.,   1.,   1.,   1.,   2.,   2.,   2.,   2.,   3.,
         3.,   3.,   3.,   4.,   4.,   4.,   4.,   5.,   5.,   5.,   5.,
    ...
       250., 250., 250., 251., 251., 251., 251., 252., 252., 252., 252.,
       253., 253., 253., 253., 254., 254., 254., 254., 255., 255.])
```
Note that the intervals at the ends are half the size, but that means that
a pixel value of 0 corresponds to -0.002 to 0.002, as opposed to 0 to 0.004
as before.
