"""
This file can be run if the dev wants to load and save all the graphs in the current directory.

This can be necessary to update a legacy set of graphs to the current version of the software.
"""
import inspect
import logging
import os

import pcot
from pcot.document import Document

logger = logging.Logger(__name__)

currentFile = inspect.getfile(inspect.currentframe())
currentDir = os.path.dirname(currentFile)
logger.info(f"Getting graphs for load/save from {currentDir}")

# get all the .pcot files in the same dir as this module
graphs = []
for root, dirs, files in os.walk(currentDir):
    for f in [x for x in files if x.lower().endswith(".pcot")]:
        graphs.append(os.path.join(root, f))

pcot.setup()

pcot.logger.setLevel(logging.ERROR)

for graphname in graphs:
    logger.critical(f"Loading and saving graph {graphname}")
    doc = Document(graphname)
    doc.run()
    # doc.save(graphname)
