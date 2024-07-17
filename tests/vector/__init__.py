"""
Test that operations involving 1D vectors work correctly. In general, operations prefer to work element-wise so
all unary operations are applied to each element of the vector.

Exceptions are made for operations that aggregate:
    mean on an image produces a vector of means for each channel
    sum on an image produces a vector of sums for each channel
    sd on an image produces a vector of standard deviations for each channel

    mean, sum or sd on a vector produces a scalar

Binary operations are a little more complex:

    on two images are applied element-wise
    on an image and a scalar: the scalar is applied to each element of the image
    on a scalar and a 1D vector: the scalar is applied to each element of the vector
    on an image and a 1D vector: each scalar in the vector is applied to the corresponding channel in the image
    on two 1D vectors: the operation is applied element-wise

With binary operations there are some constraints:
    for two vectors, the vectors must be the same length
    for an image and a vector, the vector must have the same length as the number of channels in the image
"""

