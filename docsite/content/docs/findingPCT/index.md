---
date: 2021-07-13
title: Finding the PCT
summary: This page describes how we go about locating the PCT, from the UX standpoint
tags: ["pcot","mars","python"]
---

This relies on finding a mapping from screen space to the PCT's coordinate
space and back again. Once we have such a mapping, we can find where 
the patches should be on the screen and construct a set of ROIs which
can be fine-tuned.

## Process
* Select the 3 PCT mounting screws in the image (these should be very bright).
An outline image of where the system thinks the PCT is should appear.
* Drag the PCT mounting screw points until the image matches the PCT.
* Click the "generate ROIs" button. This will (temporarily?) hide the outline,
and generate 8 regions of interest for the patches.
* Edit the regions of interest, either manually or using some set of
operations:
    * one possibility is to cluster all pixels inside the ROI, and remove those
which are outliers from the primary cluster.
* Click a button to perform line fitting
* View the uncertainties and optionally the lines
* Edit again, or accept. It should also be possible to clear the ROIs
and go back to the outline.

## Useful refs:
* [OpenCV function for getting a transform to do this](https://docs.opencv.org/3.4/da/d54/group__imgproc__transform.html#ga8f6d378f9f8eebb5cb55cd3ae295a999)



