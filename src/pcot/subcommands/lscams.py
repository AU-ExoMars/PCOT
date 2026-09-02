import numpy as np
import click

from pcot.cameras.filters import Filter
from pcot.subcommands.subcommands import cli


@cli.command(short_help="List the available cameras")
@click.option("-l", "--long", "long_", is_flag=True, help="Show long descriptions")
@click.option("-p", "--plot", is_flag=True, help="Plot the filter profiles (first camera only)")
@click.option("-f", "--filters", is_flag=True, help="Show filters")
@click.option("-F", "--file", "file_", is_flag=True,
              help="Read from a PARC file instead of the loaded PCOT cameras")
@click.argument("camera", metavar="CAMERA_NAME", required=False)
def lscams(long_, plot, filters, file_, camera):
    """
    List the available cameras in the camera directory. If CAMERA_NAME is given, just show that camera.
    """
    import pcot.cameras
    if file_:
        # we'll try to load a camera file directly here
        from pcot.cameras.camdata import CameraData
        cam = CameraData(camera)
        show(cam, long_, filters, plot)
    else:
        # we're looking at the loaded cameras, not directly inside a file.
        # first, see if there is a camera directory

        if pcot.config.getDefaultDir("cameras") is None:
            print("No camera directory set")
            return
        print(f"Camera directory: {pcot.config.getDefaultDir('cameras')}")

        # the system will not have started up fully, so we need to do this.
        pcot.config.loadCameras()

        if camera:
            cam = pcot.cameras.getCamera(camera)
            if cam is None:
                print(f"Camera {camera} not found")
            else:
                show(cam, long_, filters, plot)
        else:
            for name in pcot.cameras.getCameraNames():
                show(pcot.cameras.getCamera(name), long_, filters, plot)
                # this is a hack - we only want to show one camera if we're plotting, because
                # otherwise we get a plot for each camera.
                if plot:
                    break


def show(camera, long_, filters, plot):
    import os.path
    base_file_name = os.path.basename(camera.fileName)
    p = camera.params.params
    flag_string = ""
    if p.has_flats:
        flag_string += "F"
    print(f"{p.name:20} {base_file_name} {flag_string:>3}: {p.short}")
    if long_:
        print(f"{p.description}")
        print(f" Date from YAML file: {p.date or 'No date provided'}")
        print(f" Compilation date: {p.compilation_time or 'No date provided (earlier than 05/06/2025)'}")
        print(f" Compiled from: {p.source_filename or 'No source file provided'}")
        if p.has_flats:
            print(" Has flats")

    if filters:
        print(f"  Filters:")
        print(f"    {'Name':<5} {'Pos':<5} {'CWL':<5} {'FWHM':<5} {'transmission':14} {'more info':10}")
        for _, f in camera.params.filters.items():
            if isinstance(f, Filter):
                extra = ""
                if f.response.is_simulated:
                    extra += "(simulated)"
                if f.response.clipped_to:
                    extra += f"(clipped to {f.response.clipped_to}%)"
                print(f"    {f.name:<5} {f.position:<5} {int(f.cwl):<5} {int(f.fwhm):<5} {f.transmission:<14} {extra:10}")
            else:
                print(f"    {f} (not a filter??)")

    if plot:
        import matplotlib.pyplot as plt
        for _, f in camera.params.filters.items():
            # get the response for a range of wavelengths
            wavelengths = np.arange(300, 1200)
            if isinstance(f, Filter):
                resp = f.getResponse(wavelengths)
                label = f.name
                if f.response.is_simulated:
                    label += " (sim)"
                elif f.response.clipped_to:
                    label += f" (clipped {f.response.clipped_to}%)"

                plt.plot(wavelengths, resp, label=label)
                if f.response.clipped_to:
                    # find the part of the response that is equal to the clipped level
                    xs = np.where(np.abs(resp - f.response.clipped_to / 100) < 0.000001)[0]
                    if len(xs) > 0:
                        plt.hlines(f.response.clipped_to / 100, wavelengths[xs[0]], wavelengths[xs[-1]],
                                  linewidth=3, color="r")

        plt.title(p.name)
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Transmission")
        plt.legend()
        plt.show()
