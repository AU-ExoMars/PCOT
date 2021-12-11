import pcot
import os
import shutil

pcot.xform.createXFormTypeInstances()

if os.path.exists('docs'):
    shutil.rmtree('docs')
os.makedirs('docs')

with open("docs/index.md","w") as idxfile:
    for realname, x in pcot.xform.allTypes.items():
        name=realname.replace(' ', '_')
        idxfile.write(f"* [{realname}]({name})\n")
        print(name)
        with open(f"docs/{name}.md","w") as file:
            file.write(f"# {realname}\n")
            file.write("## Description\n")
            file.write(pcot.ui.help.getHelpMarkdown(x))
            
