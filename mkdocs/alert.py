"""
A Markdown extension for rendering blocks delineated by
multiple @-signs as alerts. I'm not using exclamation marks
because the (not as good) admonishment extension uses those.

Format:

@@@ tag
some blocks of text which will have their markdown parsed
@@@

Tags are in classNameDict, and correspond to Bootstrap alert types.

"""

from markdown import Extension
from markdown.blockprocessors import BlockProcessor
import xml.etree.ElementTree as etree
import re

classNameDict = {
    'danger' : 'alert-danger',
    'primary' : 'alert-primary',
    'secondary' : 'alert-secondary',
    'warning' : 'alert-warning',
    'info' : 'alert-info'
}   

class AlertBlockProcessor(BlockProcessor):
    RE_FENCE_START = r'^ *@{3,} *([a-z]*) *\n' # start line, e.g., `   !!!! `
    RE_FENCE_END = r'\n *@{3,}\s*$'  # last non-blank line, e.g, '!!!\n  \n\n'

    def test(self, parent, block):
        return re.match(self.RE_FENCE_START, block)

    def run(self, parent, blocks):
        original_block = blocks[0]
        matches = re.match(self.RE_FENCE_START, blocks[0])
        name = matches.group(1)
        
        className = classNameDict.get(name,classNameDict['danger'])
        
        blocks[0] = re.sub(self.RE_FENCE_START, '', blocks[0])

        # Find block with ending fence
        for block_num, block in enumerate(blocks):
            if re.search(self.RE_FENCE_END, block):
                # remove fence
                blocks[block_num] = re.sub(self.RE_FENCE_END, '', block)
                # render fenced area inside a new div
                e = etree.SubElement(parent, 'div')
                e.set('class', 'alert '+className)
                e.set('role', 'alert')
                self.parser.parseBlocks(e, blocks[0:block_num + 1])
                # remove used blocks
                for i in range(0, block_num + 1):
                    blocks.pop(0)
                return True  # or could have had no return statement
        # No closing marker!  Restore and do nothing
        blocks[0] = original_block
        return False  # equivalent to our test() routine returning False

class AlertExtension(Extension):
    def extendMarkdown(self, md):
        md.parser.blockprocessors.register(AlertBlockProcessor(md.parser), 'alert', 175)


def makeExtension(*args, **kwargs):
    return AlertExtension(**kwargs)
