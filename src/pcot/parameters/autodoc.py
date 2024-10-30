"""Autodocumentation generator for tagged aggregate types.

First we generate a tree from the TaggedDict at the root using build_tree, then
we convert that tree into an HTML table using output_as_table. A mermaid generator
is also provided; it was used in testing.

"""
from typing import List, Union, Optional

from pcot.parameters.taggedaggregates import TaggedListType, TaggedDictType, Maybe, TaggedVariantDictType, \
    TaggedAggregateType


class TreeNode:
    name: str
    column: int
    rowspan: int
    row: int
    unique_id: int
    children: List['TreeNode']
    desc: Optional[str]
    optional: bool
    parent: Optional['TreeNode']

    count = 0

    def __init__(self, name: str, desc: Optional[str], optional: bool):
        self.name = name
        self.desc = desc
        self.optional = optional
        self.children = []
        self.row = -1
        self.column = -1
        self.rowspan = -1
        self.rowbuffer = 0      # holds the row value of the parent while we calculate the row value of the children
        self.unique_id = TreeNode.count
        self.parent = None
        TreeNode.count += 1

    def add(self, child: 'TreeNode'):
        self.children.append(child)
        child.parent = self

    def mermaid(self):
        # output a mermaid diagram, which each link on a separate line to make it
        # easier to read.
        def _mermaid(node: 'TreeNode', lines: List[str]):
            desc = f"\n{node.desc}" if node.desc else ""
            name = f"{node.name} (optional)" if node.optional else node.name
            lines.append(f"{node.unique_id}[\"{name}{desc}\"]")
            for child in node.children:
                lines.append(f"{node.unique_id} --> {child.unique_id}")
                _mermaid(child, lines)

        lines = ["", "", "", "flowchart"]
        _mermaid(self, lines)
        return "\n".join(lines) + "\n\n\n"

    def __str__(self):
        return f"TreeNode({self.name}, row {self.row}, span {self.rowspan})"


def build_tree(agg: Union[type, TaggedAggregateType], name: str, desc: Optional[str]) -> TreeNode:
    if isinstance(agg, Maybe):
        optional = True
        agg = agg.type_if_exists
    else:
        optional = False

    if not isinstance(agg, TaggedAggregateType):
        # if this is a node for a plain type, we create a node for name and type immediately
        return TreeNode(f"{agg.__name__} {name}", desc, optional)
    elif isinstance(agg, TaggedDictType):
        # we need to detect the special case where we have a fixed dict of numbered items (e.g. inputs) which are
        # all the same
        root = TreeNode(name, desc, optional)
        keys = list(agg.tags.keys())
        vals = [x.type for x in agg.tags.values()]
        snark = vals.count(vals[0])
        if keys[0].isdigit() and vals.count(vals[0]) == len(vals):
            # we have a fixed dict of numbered items - all we need to do is create a node for the first item
            # with a name that indicates the range (e.g. "0-3"). First get that name.
            first = int(keys[0])
            last = first + len(keys) - 1
            tag = agg.tags[keys[0]]
            root.add(build_tree(tag.type, f"{first}-{last}", tag.description))
        else:
            # otherwise we create a node for each key
            for key, tag in agg.tags.items():
                root.add(build_tree(tag.type, key, tag.description))
    elif isinstance(agg, TaggedListType):
        # Note that here we are IGNORING the desc field set inside the list, and using the desc field assigned
        # to the list item the parent dict. TaggedListTypes shouldn't really have descriptions in their single tag.
        if not isinstance(agg.tag().type, TaggedAggregateType):
            root = TreeNode(f"{agg.tag().type.__name__} {name}[]", desc, optional)
        else:
            root = build_tree(agg.tag().type, name + "[]", desc)
    elif isinstance(agg, TaggedVariantDictType):
        root = TreeNode(name, desc, optional)
        disc = agg.discriminator_field
        for key, tp in agg.type_dict.items():
            root.add(build_tree(tp, f"{disc}={key}", None))
    else:
        raise ValueError(f"Unknown type {agg}")
    return root


def calculate_positions(root: TreeNode):
    # We need to traverse the tree, making sure the column of each node is equal to its depth.
    # We also need to calculate the rowspan of each node (the total number of children it has in all branches)
    # and the row of each node, which is calculated from the row of the parent.

    max_column = 0

    def _calc(node: TreeNode, depth: int):
        nonlocal max_column
        node.column = depth
        if depth > max_column:
            max_column = depth
        total = 0  # total number of children in all branches
        for child in node.children:
            total += _calc(child, depth + 1)
        if total == 0:
            total = 1  # if we have no children, we still need to have a rowspan of 1!
        node.rowspan = total
        return total

    _calc(root, 0)

    # and traverse again, this time allocating the row. This needs to be done in a breadth-first manner.

    queue = [root]
    max_row = 0
    while queue:
        node = queue.pop(0)         # get the next node
        if node.parent is None:     # if it's the root, the row is zero
            node.row = 0
            node.rowbuffer = 0
        else:
            node.row = node.parent.rowbuffer        # otherwise, it's the row of the parent
            node.rowbuffer = node.row               # we store this in the buffer so we can calculate the row of the children
            # and we modify it because we have taken up some rows - but we dont' want to modify the parent's actual row!
            node.parent.rowbuffer += node.rowspan
        queue.extend(node.children)     # add the children to the queue
        if node.row > max_row:
            max_row = node.row
    return max_row, max_column


def output_as_table(root: TreeNode):
    # print the tree as an HTML table
    max_row, max_column = calculate_positions(root)
    out = f"<table border='1' style='border-collapse: collapse;'>"

    def find_node(node: TreeNode, col: int, row: int) -> Optional[TreeNode]:
        if node.column == col and node.row == row:
            return node
        for child in node.children:
            found = find_node(child, col, row)
            if found is not None:
                return found
        return None

    for row in range(max_row+1):
        out += "<tr>"
        for col in range(max_column + 1):
            node = find_node(root, col, row)
            if node:
                out += f'<td rowspan="{node.rowspan}" style="border-right: none;">{node.name}</td>'
                if node.desc:
                    out += f'<td rowspan="{node.rowspan}" style="border-left: none;">{node.desc}</td>'
        out += "</tr>"
    out += "</table>"
    return out


def generate_outputs_documentation():
    """Generate documentation for the outputs."""
    from pcot.parameters.runner import outputDictType
    root = build_tree(outputDictType, "outputs", None)
    return output_as_table(root)


def generate_inputs_documentation():
    """Generate documentation for the inputs."""
    from pcot.parameters.inputs import inputsDictType
    root = build_tree(inputsDictType, "inputs", None)
    return output_as_table(root)


def generate_node_documentation(nodeName: str):
    """Generate documentation for a node type; pcot.setup() must have been called"""
    from pcot.xform import allTypes
    t = allTypes.get(nodeName)
    if t.params is None:
        return f"No automatic parameter documentation available for {nodeName}"
    root = build_tree(t.params, nodeName, None)
    return output_as_table(root)


def test_tree():
    import pcot
    from pcot.parameters.inputs import inputsDictType
    from pcot.xforms.xformmultidot import XFormMultiDot
    pcot.setup()
    s = generate_node_documentation("multidot")

    with open("c:/users/jim/out.html","w") as f:
        f.write(s)
