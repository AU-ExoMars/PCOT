---
date: 2021-07-13
title: Glossary
summary: Some terminology
tags: ["pcot","mars","python"]
---

{{<katex>}}

### IoF
The ratio of the bidirectional
reflectance of a surface to that of a normally illuminated
perfectly diffuse surface. This ratio is also known as the 'radiance 
factor'.IOF is equal to $\frac{i}{\pi f}$ where $i$ is equal to the measured
scene radiance, and $\pi f$ is the solar irradiance at the top of the
Martian atmosphere for a given Pancam bandpass.
[From the PDS
docs](https://pds.nasa.gov/ds-view/pds/viewProfile.jsp?dsid=MER2-M-PANCAM-3-IOFCAL-SCI-V1.0).
Useful because lots of other probes use it!

### R\*
Used by Mars Pathfinder (Reid, 1999[^2]). 
> A related parameter, R* (''R-star''), was defined and
utilized by Reid et al. [1999] for Imager for Mars Pathfinder
(IMP) reflectance products. R* was defined by Reid et al.
[1999] as ''the brightness of the surface divided by the
brightness of an RT (Radiometric Calibration Target) scaled
to its equivalent Lambert reflectance.'' Some researchers
have called this quantity ''relative reflectance'' because it is
the reflectance of the scene relative to that of a perfectly
Lambertian albedo = 1.0 surface in an identical geometry. In
general, R* can be defined as the ratio of the reflectance of a
surface to that of a perfectly diffuse surface under the same
conditions of illumination and measurement. This is also
known as the reflectance factor or reflectance coefficient
[Hapke, 1993], and it is essentially an approximation of the
Lambert albedo within each Pancam bandpass. Units of R*
can be obtained by dividing Pancam IOF images by the
cosine of the solar incidence angle at the time of the
observation.

> R* is useful in that it allows for direct comparison
between spectra taken at different times of day, and more
straightforward comparison with laboratory spectra. Images
calibrated to R* also have the advantage of being at least
partially ''atmospherically corrected,'' because observations
of the Pancam calibration target also include the average
diffuse sky illumination component of the scene radiance

> It should be
noted that IOF and R* differ only by a constant multiplicative scaling factor, and not in the shape of their spectra, as
long as all of the images in a multispectral sequence are
acquired in rapid-enough succession that there have not
been significant variations in solar incidence angle as a
function of wavelength[^2].

So effectively,
$$
R^* = \frac{IoF}{\cos i}
$$
Oddly, though, we also have 
$$
IoF = r\cdot m \cdot \cos(i)
$$from [2] (Eq. 35), where $r$ is the radiance. So
$$
R^* = r m \quad\text{?}
$$

[^1]: [Allender, Elyse J., et al. "The ExoMars spectral tool (ExoSpec): An image analysis tool for ExoMars 2020 PanCam imagery." Image and Signal Processing for Remote Sensing XXIV. Vol. 10789. International Society for Optics and Photonics, 2018.](https://research-repository.st-andrews.ac.uk/bitstream/handle/10023/16973/Allender_2018_ExoMars_SPIE_107890I.pdf)
[^2]: [Bell III, James F., et al. "In-flight calibration and performance of the Mars Exploration Rover Panoramic Camera (Pancam) instruments." Journal of Geophysical Research: Planets 111.E2 (2006).](https://agupubs.onlinelibrary.wiley.com/doi/pdfdirect/10.1029/2005JE002444)
    
