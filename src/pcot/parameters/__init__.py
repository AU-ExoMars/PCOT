"""
This package contains code involved with parameter files - files that store modifications to a graph which
can be applied as the graph is loaded.

This mechanism involved TaggedAggregate structures, which are a principled and self-describing way to store
data for serialisation; and the ParameterHandler class, which reads a parameter file and can apply its changes
to one or more sets of TaggedAggregates.
"""


