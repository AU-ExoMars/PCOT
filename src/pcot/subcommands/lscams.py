from pcot.subcommands import subcommand, argument


@subcommand([
    argument("--long","-l", help="Show long descriptions", action="store_true"),
    argument("--filters","-f", help="Show filters", action="store_true"),
    argument("--file","-F", help="Read from a PARC file instead of the loaded PCOT cameras", action="store_true"),
    argument("camera", metavar="CAMERA_NAME", help="Camera name", nargs="?")
    ],
    shortdesc="List the available cameras")
def lscams(args):
    """List the available cameras in the camera directory. If a camera name is given, just show that camera.
    """
    import pcot.cameras
    if args.file:
        # we'll try to load a camera file directly here
        from pcot.cameras.camdata import CameraData
        camera = CameraData(args.camera)
        show(camera, args)
    else:
        # we're looking at the loaded cameras, not directly inside a file.
        # first, see if there is a camera directory

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
    import os.path
    base_file_name = os.path.basename(camera.fileName)
    p = camera.params.params
    flag_string = ""
    if p.has_reflectances:
        flag_string += "R"
    if p.has_flats:
        flag_string += "F"
    print(f"{p.name:20} {base_file_name} {flag_string:>3}: {p.short}")
    if args.long:
        print(f"{p.description}")
        print(f" Date from YAML file: {p.date or 'No date provided'}")
        print(f" Compilation date: {p.compilation_time or 'No date provided (earlier than 05/06/2025'}")
        print(f" Compiled from: {p.source_filename or 'No source file provided'}")
        if p.has_reflectances:
            print(f" Reflectances supported: {', '.join(camera.getReflectances().keys())}")
        if p.has_flats:
            print(" Has flats")

    if args.filters:
        print(f"  Filters:")
        print(f"    {'Name':<5} {'Pos':<5} {'CWL':<5} {'FWHM':<5} {'transmission':14}")
        for _, f in camera.params.filters.items():
            print(f"    {f.name:<5} {f.position:<5} {int(f.cwl):<5} {int(f.fwhm):<5} {f.transmission:<14}")


