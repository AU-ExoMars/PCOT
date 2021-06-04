"""
Contains deprecated Xform types, which won't be automatically loaded and registered because they are in
a subdirectory. Later on we might permit subdirectory walking with os.walk, so xform types can be in
a tree. In that case, we should check the "deprecated" case.
"""