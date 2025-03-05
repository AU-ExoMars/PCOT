from pcot.subcommands import subcommand, argument


@subcommand([
    argument("--long","-l", help="Show long descriptions", action="store_true"),
    argument("--filters","-f", help="Show filters", action="store_true"),
    argument("camera", metavar="CAMERA_NAME", help="Camera name", nargs="?")
    ],
    shortdesc="List the available cameras")
def lscams(args):
    """List the available cameras in the camera directory. If a camera name is given, just show that camera.
    """
    # first, see if there is a camera directory
    import pcot.config
    import pcot.cameras

    if pcot.config.getDefaultDir("cameras") is None:
        print("No camera directory set")
        return
    print(f"Camera directory: {pcot.config.getDefaultDir('cameras')}")

    # the system will not have started up fully, so we need to do this.
    pcot.config.loadCameras()

    if args.camera:
        camera = pcot.cameras.getCamera(args.camera)
        if camera is None:
            print(f"Camera {args.camera} not found")
        else:
            show(camera, args)
    else:
        for name in pcot.cameras.getCameraNames():
            show(pcot.cameras.getCamera(name),args)


def show(camera, args):
    print(f"{camera.params.params.name:20}: {camera.params.params.short}")
    if args.long:
        print(f"{camera.params.params.description}")
    if args.filters:
        print(f"  Filters:")
        print(f"    {'Name':<5} {'Pos':<5} {'CWL':<5} {'FWHM':<5} {'transmission':14}")
        for _, f in camera.params.filters.items():
            print(f"    {f.name:<5} {f.position:<5} {int(f.cwl):<5} {int(f.fwhm):<5} {f.transmission:<14}")


