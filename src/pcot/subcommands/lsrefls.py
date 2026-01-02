import pydoc

import numpy as np

import pcot.cameras
from pcot.cameras import reflectances
from pcot.subcommands import argument, subcommand


@subcommand([
    argument("--long","-l", help="Show long descriptions", action="store_true"),
    argument("--plot","-p", help="Plot the responses (first target only)", action="store_true"),
    argument("--filters","-f", help="Show filters", action="store_true"),
    argument("--file","-F", help="Read from a PARC file instead of the loaded reflectances", action="store_true"),
    argument("reflectance", metavar="REFLECTANCE_TARGET_NAME", help="Reflectance target name", nargs="?")
    ],
    shortdesc="List the available reflectance targets"
)
def lsrefls(args):
    """List the available reflectance targets in the reflectances directory."""
    from pcot import config
    from pcot.cameras import reflectances
    if args.file:
        # we'll try to load a file directly here
        refl = reflectances.load(args.file)
        show(refl, args)
    else:
        # otherwise we're looking at loaded reflectances.
        if config.getDefaultDir("reflectances") is None:
            print("No reflectance directory set")
            return
        print(f"Reflectance target directory: {config.getDefaultDir('reflectances')}")

        # the system won't have started up fully, so we do this.
        config.loadReflectances()

        if args.reflectance:
            refl = pcot.cameras.getReflectance(args.reflectance)
            if refl is None:
                print(f"Reflectance target {args.reflectance} not found")
            else:
                show(refl, args)
        else:
            for name in pcot.cameras.getReflectanceNames():
                show(pcot.cameras.getReflectance(name), args)
                if args.plot:
                    break  # we only do the first one if plotting


def show(r, args):
    import os.path
    if r.path is None:
        base_file_name = "(unsaved)"
    else:
        base_file_name = os.path.basename(r.path)

    print(f"{r.metadata.name:20} {base_file_name}: {r.typename}, {r.metadata.short}")

    if args.long:
        print(f"Compilation date: {r.metadata.date}")
        print(r.metadata.description)
        for p in r.get_patches():
            phi_range, theta_range, wvl_range = r.get_range(p)
            print(f" {p}: Phi [{phi_range[0]}:{phi_range[1]}], Theta [{theta_range[0]}:{theta_range[1]}], Wavelength [{wvl_range[0]}:{wvl_range[1]}]")
        print()

    if args.plot:
        import matplotlib.pyplot as plt
        for p in r.get_patches():
            phi_range, theta_range, wvl_range = r.get_range(p)
            theta = 0       # straight on
            phi = 270       # this is looking at the PCT along its vertical axis
            wvls, data = r.get_reflectances(p, phi=phi, theta=theta, clip=True)
            plt.plot(wvls, data, label=p)
        plt.title(r.metadata.name)
        plt.xlabel("Wavelength (nm)")
        plt.ylabel("Reflectance")
        plt.legend()
        plt.show()

