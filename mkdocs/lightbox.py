"""
A Markdown extension which converts images into lightboxes. To use,
put an extra ! in front of the text description of an image:

![The PCOT user interface](app.png)

becomes

![!The PCOT user interface](app.png)


This was adapted from https://github.com/g-provost/lightgallery-markdown
and some of the options don't work, because I'm using Lightbox2.

"""

from markdown import Extension
from markdown.treeprocessors import Treeprocessor
import xml.etree.ElementTree as etree
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
                if '|' in desc:
                    desc,anchor = desc.split('|',2)
                else:
                    anchor = None
                image.set("alt", desc)
                parent = parent_map[image]
                ix = list(parent).index(image)
                top = etree.Element('figure', attrib={"class": "text-center"})
                new_node = etree.SubElement(top,'a')
                new_node.set("href", image.attrib["src"])
                if anchor is not None:
                    new_node.set("name", anchor)
                new_node.set("data-lightbox",image.attrib["src"])
                if self.config["show_description_as_inline_caption"]:
                    inline_caption_node = etree.Element('p')
                    inline_caption_node.set("class", self.config["custom_inline_caption_css_class"])
                    inline_caption_node.text = desc
                    parent.insert(ix + 1, inline_caption_node)
                new_node.append(image)
                caption = etree.Element('figcaption',attrib={"class":"figure-caption text-center"})
                caption.text=f"Figure: {desc}. Click on image to expand."
                top.insert(1,caption)
                parent.insert(ix, top)
                parent.remove(image)

class LightBoxExtension(Extension):
    def __init__(self, **kwargs):
        self.config = {
            'show_description_in_lightbox' : [True, 'Adds the description as caption in lightbox dialog. Default: True'],
            'show_description_as_inline_caption' : [False, 'Adds the description as inline caption below the image. Default: False'],
            'custom_inline_caption_css_class' : ['', 'Custom CSS classes which are applied to the inline caption paragraph. Multiple classes are separated via space. Default: empty']
        }
        super(LightBoxExtension, self).__init__(**kwargs)


    def extendMarkdown(self, md):
        config = self.getConfigs()
        md.treeprocessors.register(ImagesTreeprocessor(config, md), "lightbox", 5)  # must be processed LATE.


def makeExtension(*args, **kwargs):
    return LightBoxExtension(**kwargs)

