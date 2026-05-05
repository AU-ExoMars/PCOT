"""
Configuration management UI, using TaggedAggregate values.
"""
import json
import sys
from pathlib import Path

from PySide2 import QtWidgets

from pcot.parameters.taggedaggregates import TaggedDictType, Maybe, TaggedListType, TaggedDict, TaggedVariantDictType
from pcot.ui.taggedaggregates import AggregateEditorDialog

DUMMY = TaggedDictType(
    aa=("Test string", Maybe(str), "teststringdefault"),
    ab=("Test string 2", Maybe(str), "teststringdefault 2 asdasd asd asd  asd "),
    ac=("Nullable int", Maybe(int), 3),
).setOrdered()


VARDICT1 = TaggedDictType(
    type=("type", str, "vardict1", ["vardict1", "vardict2"]),
    vd1data=("Nullable int", Maybe(int), 3),
    aa=("Test string", Maybe(str), "teststringdefault"),
    ab=("Test string 2", Maybe(str), "teststringdefault 2 asdasd asd asd  asd "),
    ac=("Nullable int", Maybe(int), 3),
).setOrdered()

VARDICT2 = TaggedDictType(
    type=("type", str, "vardict2", ["vardict1", "vardict2"]),
    vd2data=("float", float, 3),
).setOrdered()

VARIANTDICT = TaggedVariantDictType("type",
                                    {
                                        "vardict1": VARDICT1,
                                        "vardict2": VARDICT2,
                                    }, default_type_name="vardict1",

                                    )

TESTCONFIG = TaggedDictType(
    path=("File path", Maybe(Path), None, "PCOT files (*.pcot *.jpg)"),
    path2=("Any file path", Path, "d:/", None),
    v=("Variant test", VARIANTDICT, None),
    dir=("Dir path", Maybe(Path), None, True),
    btest=("boolean", Maybe(bool), False),
    aa=("Test string", str, "teststringdefault"),
    a=("Test string", str, "teststringdefault"),
    b=("Test string 2", str, "teststringdefault 2 asd asdasd asdasd"),
    nullable=("Nullable int", Maybe(int), 3, (0,200)),
    d =("Choices", Maybe(str), "foo", ("foo", "bar", "baz")),
    e=("Test string", str, "teststringdefault"),
    lst=("List", TaggedListType(Maybe(Path),[Path(f"foo{i}") for i in range(20)],None)),
    subdict1=("subdict",
              TaggedDictType(
                p=("Foo", str, "foo"),
                q=("Bar", str, "bar", ["bing","bong","bar"]),
                x=("File test", Path, Path()),
                zz=("internal", DUMMY, None),
                zz2=("internal", DUMMY, None),
                zz3=("internal", DUMMY, None),
                zz4=("internal", DUMMY, None),
                zz5=("internal", DUMMY, None),
                r=("Baz", int, 4)).setOrdered(),None),
    arglist=("Argument list",TaggedListType(
                 TaggedDictType(
                    name=("Name",str,"name"),
                    datatype=("Type",str,"int",["int","float"]),
                    deflt=("Default",Maybe(str),None)
                ).setOrdered(),0))
).setOrdered()


testconfig = TaggedDict(TESTCONFIG)


def runConfigUI():
    """This is the function that runs the configuration UI on the main config TaggedDict"""
    import pcot
    dialog = AggregateEditorDialog(pcot.config.data)
    dialog.exec_()  # it's modal
    if dialog.data():
        pcot.ui.log("Setting changes accepted")
        pcot.config.data = dialog.data()
        pcot.config.save()
    else:
        pcot.ui.log("Setting changes rejected")

def runtest():
    import pcot.config
    app = QtWidgets.QApplication(sys.argv)

    # change this in testing
    if True:
        config = testconfig
    else:
        config = pcot.config.data


    # smoke test
    dd = config.serialise()
    config = TESTCONFIG.deserialise(dd)

    while True:
        import yaml
        dialog = AggregateEditorDialog(config)
        dialog.exec_()
        if dialog.data():
            print("Accepted")
            config = dialog.data()
        s = yaml.dump(config.serialise(forceUnordered=True))
        s = yaml.safe_load(s)
        config = TESTCONFIG.deserialise(s)
        print(json.dumps(config.serialise(forceUnordered=True), indent=2))
        if not dialog.data():
            break

if __name__ == "__main__":
    runtest()



