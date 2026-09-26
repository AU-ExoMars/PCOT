This file contains global test data which can be accessed using
the globaldatadir fixture:
```python
with (globaldatadir / 'zog.dat').open():
    ...
```

## PNG test images
These are from http://www.schaik.com/pngsuite/pngsuite_bas_png.html

* basn0g01 - black & white
* basn0g02 - 2 bit (4 level) grayscale
* basn0g16 - 16 bit (64k level) grayscale
* basn2c16 - 3x16 bits rgb color

## Ancillary data sidecars
In `ancillary`: a real AUPE3 sidecar file (`aupe3_sidecar.png.xml` - LWAC filter 4, exposure_time
0.009911), used by `tests/input/test_multifile_sidecars.py` as a template for sidecars with other
exposure times.
