#!/usr/bin/env python
# -*- coding: utf8 -*-
import sys
import getopt
import pprint
import json

from solum import JarFile, ClassFile, ConstantType

def first_pass(buff):
    """
    The first pass across the JAR will identify all possible classes it
    can, maping them by the 'type' it implements.

    We have limited information available to us on this pass. We can only
    check for known signatures and predictable constants. In the next pass,
    we'll have the initial mapping from this pass available to us.
    """
    # str_as_buffer is required, else it'll treat the string buffer
    # as a file path.
    cf = ClassFile(buff, str_as_buffer=True)

    # First up, finding the "block superclass" (as we'll call it).
    # We'll look for one of the debugging messages.
    const = cf.constants.find_one(
        ConstantType.STRING,
        lambda c: "when adding" in c["string"]["value"]
    )

    if const:
        # We've found the block superclass, all done.
        return ("block_superclass", cf.this)

    # Next up, see if we've got the packet superclass in the same way.
    const = cf.constants.find_one(
        ConstantType.STRING,
        lambda c: "Duplicate packet" in c["string"]["value"]
    )

    if const:
        # We've found the packet superclass.
        return ("packet_superclass", cf.this)

    # The individual packet classes have a unique signature.
    pread = cf.methods.find_one(args=("java.io.DataInputStream",))
    pwrite = cf.methods.find_one(args=("java.io.DataOutputStream",))
    size = cf.methods.find_one(returns="int", args=())

    if pread and pwrite and size:
        return ("packet", cf.this)

    # The main recipe superclass.
    const = cf.constants.find_one(
        ConstantType.STRING,
        lambda c: "X#X" in c["string"]["value"]
    )

    if const:
        return ("recipe_superclass", cf.this)

    # First of 2 auxilary recipe classes. Appears to be items with
    # inventory, + sandstone.
    const = cf.constants.find_one(
        ConstantType.STRING,
        lambda c: c["string"]["value"] == "# #"
    )

    if const:
        return ("recipe_inventory", cf.this)

    # Second auxilary recipe class. Appears to be coloured cloth?
    const = cf.constants.find_one(
        ConstantType.STRING,
        lambda c: c["string"]["value"] == "###"
    )

    if const:
        return ("recipe_cloth", cf.this)

def packet_ids(jar, name):
    """
    Get all of the packet ID's for each class.
    """
    cf = ClassFile(jar[name], str_as_buffer=True)
    
    ret = {}
    stack = []
    static_init = cf.methods.find_one(name="<clinit>")

    for ins in static_init.instructions:
        # iconst_N (-1 => 5) push N onto the stack
        if ins.name.startswith("iconst"):
            stack.append(int(ins.name[-1]))
        # [bs]ipush push a byte or short (respectively) onto the stack
        elif ins.name.endswith("ipush"):
            stack.append(ins.operands[0][1])
        elif ins.name == "ldc":
            const_i = ins.operands[0][1]
            const = cf.constants[const_i]
            name = const["name"]["value"]

            client = stack.pop()
            server = stack.pop()
            id_ = stack.pop()

            ret[name] = {"id": id_, "from_client": bool(client), "from_server": bool(server)}

    return ret

def stats_US(jar):
    """
    Get's statistics and achievements names and descriptions.
    """
    ret = dict(stat={}, achievement={})
    # Get the contents of the stats language file
    sf = jar["lang/stats_US.lang"]
    sf = sf.split("\n")
    for line in sf:
        line = line.strip()
        if not line:
            continue

        tag, desc = line.split("=", 1)
        category, name = tag.split(".", 1)

        if category == "stat":
            ret["stat"][name] = desc
        elif category == "achievement":
            real_name = name[:-5] if name.endswith(".desc") else name
            if real_name not in ret["achievement"]:
                ret["achievement"][real_name] = {}

            if name.endswith(".desc"):
                ret["achievement"][real_name]["desc"] = desc
            else:
                ret["achievement"][name]["name"] = desc

    return ret

def main(argv=None):
    if not argv:
        argv = []

    verbose = False
    output = sys.stdout

    try:
        opts, args = getopt.gnu_getopt(argv, "o:v", ["output="])
    except getopt.GetoptError, err:
        print str(err)
        sys.exit(1)

    for o, a in opts:
        if o == "-v":
            verbose = True
        elif o in ("-o", "--output"):
            output = open(a, "wb")

    for i,arg in enumerate(args, 1):
        out = {}
        jar = JarFile(arg)

        # The first pass aims to map as much as we can immediately, so we
        # what is where without having to do constant iterations.
        mapped = jar.map(first_pass, parallel=True)
        out["class_map"] = mapped = filter(lambda f: f, mapped)

        # Get the statistics and achievement text
        out.update(stats_US(jar))

        # Get the packet ID's (if we know where the superclass is)
        for type_, name in out["class_map"]:
            if type_ == "packet_superclass":
                out["packets"] = packet_ids(jar, "%s.class" % name)
                break

        json.dump(out, output, sort_keys=True, indent=4)
        output.write("\n")

    if output is not sys.stdout:
        output.close()

if __name__ == "__main__":
    main(sys.argv[1:])