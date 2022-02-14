from markdown import Extension
from markdown.treeprocessors import Treeprocessor
from markdown.util import etree
import re


class ImagesTreeprocessor(Treeprocessor):
    def __init__(self, config, md):
        Treeprocessor.__init__(self, md)
        self.re = re.compile(r'^!.*')
        self.config = config

    def run(self, root):
        parent_map = {c: p for p in root.iter() for c in p}
        try:
            images = root.iter("img")
        except AttributeError:
            images = root.getiterator("img")
        for image in images:
            desc = image.attrib["alt"]
            if self.re.match(desc):
                desc = desc.lstrip("!")
                image.set("alt", desc)
                parent = parent_map[image]
                ix = list(parent).index(image)
                new_node = etree.Element('a')
                new_node.set("href", image.attrib["src"])
                new_node.set("data-lightbox",image.attrib["src"])
                if self.config["show_description_as_inline_caption"]:
                    inline_caption_node = etree.Element('p')
                    inline_caption_node.set("class", self.config["custom_inline_caption_css_class"])
                    inline_caption_node.text = desc
                    parent.insert(ix + 1, inline_caption_node)
                new_node.append(image)
                parent.insert(ix, new_node)
                parent.remove(image)

class LightBoxExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            'show_description_in_lightbox' : [True, 'Adds the description as caption in lightbox dialog. Default: True'],
            'show_description_as_inline_caption' : [False, 'Adds the description as inline caption below the image. Default: False'],
            'custom_inline_caption_css_class' : ['', 'Custom CSS classes which are applied to the inline caption paragraph. Multiple classes are separated via space. Default: empty']
        }
        super(LightBoxExtension, self).__init__(**kwargs)


    def extendMarkdown(self, md, md_globals):
        config = self.getConfigs()
        md.treeprocessors.add("lightbox", ImagesTreeprocessor(config, md), "_end")


def makeExtension(*args, **kwargs):
    return LightBoxExtension(**kwargs)

