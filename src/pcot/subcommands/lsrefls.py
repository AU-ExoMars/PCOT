import click

import pcot.cameras
from pcot.cameras import reflectances
from pcot.subcommands.subcommands import cli


@cli.command(short_help="List the available reflectance targets")
@click.option("-l", "--long", "long_", is_flag=True, help="Show long descriptions")
@click.option("-p", "--plot", is_flag=True, help="Plot the responses (first target only)")
@click.option("-F", "--file", "file_", is_flag=True,
              help="Read from a PARC file instead of the loaded reflectances")
@click.argument("reflectance_target_name", required=False)
def lsrefls(long_, plot, file_, reflectance_target_name):
    """List the available reflectance targets in the reflectances directory."""
    from pcot import config
    from pcot.cameras import reflectances
    if file_:
        # we'll try to load a file directly here
        refl = reflectances.load(reflectance_target_name)
        show(refl, long_, plot)
    else:
        # otherwise we're looking at loaded reflectances.
        if config.getDefaultDir("reflectances") is None:
            print("No reflectance directory set")
            return
        print(f"Reflectance target directory: {config.getDefaultDir('reflectances')}")

        # the system won't have started up fully, so we do this.
        config.loadReflectances()

        if reflectance_target_name:
            refl = pcot.cameras.getReflectance(reflectance_target_name)
            if refl is None:
                print(f"Reflectance target {reflectance_target_name} not found")
            else:
                show(refl, long_, plot)
        else:
            for name in pcot.cameras.getReflectanceNames():
                show(pcot.cameras.getReflectance(name), long_, plot)
                if plot:
                    break  # we only do the first one if plotting


def show(r, long_, plot):
    import os.path
    if r.path is None:
        base_file_name = "(unsaved)"
    else:
        base_file_name = os.path.basename(r.path)

    print(f"{r.metadata.name:20} {base_file_name}: {r.typename}, {r.metadata.short}")

    if long_:
        print(f"Compilation date: {r.metadata.date}")
        print(r.metadata.description)
        for p in r.get_patches():
            phi_range, theta_range, wvl_range = r.get_range(p)
            print(f" {p}: Phi [{phi_range[0]}:{phi_range[1]}], Theta [{theta_range[0]}:{theta_range[1]}], Wavelength [{wvl_range[0]}:{wvl_range[1]}]")
        print()

    if plot:
        import matplotlib.pyplot as plt
        for p in r.get_patches():
            phi_range, theta_range, wvl_range = r.get_range(p)
            theta = 0       # straight on
            phi = 270       # this is looking at the PCT along its vertical axis
            wvls, data = r.get_reflectances(p, phi=phi, theta=theta)
            plt.plot(wvls, data, label=p)
        plt.title(r.metadata.name)
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Reflectance")
        plt.legend()
        plt.show()
