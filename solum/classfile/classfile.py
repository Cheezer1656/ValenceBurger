#!/usr/bin/env python
# -*- coding: utf8 -*-
"""
Copyright (c) 2010-2011 Tyler Kennedy <tk@tkte.ch>

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in
all copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
THE SOFTWARE.
"""
from struct import calcsize, unpack_from

from .constants import ConstantPool
from .fields import FieldTable
from .methods import MethodTable 
from .attributes import AttributeTable

class ClassError(Exception):
    """
    Raised as a generic exception when a class parsing or class
    specification violation is encounter.
    """

class ClassFile(object):
    """
    Todo: Needs better documentation! 
    """
    def __init__(self, str_or_file, str_as_buffer=False):
        """
        Loads an existing .class file from `str_or_file`. By default, treat
        `str_or_file` as either a path to a file or as a file-like object.
        If `str_as_buffer` is True, assume `str_or_file` is the valid contents
        of a class file.
        """
        if str_as_buffer:
            self._load_from_buffer(str_or_file)
        elif hasattr(str_or_file, "read"):
            self._load_from_file(str_or_file)
        else:
            self._load_from_path(str_or_file)

    def _load_from_path(self, path):
        fin = open(path, "rb")
        self._load_from_file(fin)
        fin.close()

    def _load_from_file(self, fin):
        tmp = fin.read()
        self._load_from_buffer(tmp)
        del tmp

    def _load_from_buffer(self, buff):
        self._pos = 0
        def src(format):
            length = calcsize(format)
            tmp = unpack_from(format, buff, self._pos)
            self._pos += length
            return tmp[0] if len(tmp) == 1 else tmp

        magic = src(">I")
        if magic != 0xCAFEBABE:
            raise ClassError("invalid class file")

        ver_min, ver_major = src(">HH")
        self.version = (ver_major, ver_min)
    
        self._load_constant_pool(src)

        self.flags, this, superclass, if_count = src(">HHHH")

        self.this = self.constants[this]["name"]["value"]
        self.superclass = self.constants[superclass]["name"]["value"]

        self._interfaces = src(">%sH" % if_count)

        self._fields = FieldTable(src, self._constants)

        self._methods = MethodTable(src, self._constants)
        
        self._attributes = AttributeTable(src, self._constants)

    def _load_constant_pool(self, _):
        """
        While this method may seem a bit convoluted, it is by the 
        fastest solution of the ones I've tested. However, in
        comparison to the rest of Solum, it is still one of the
        slowest methods. Have a better solution? Contribute it!
        """
        constant_pool_count = _(">H")
        constant_pool = ConstantPool() 

        x = 1
        while x < constant_pool_count:
            tag = _(">B") # The type of constant
            if tag == 7:
                constant_pool[x] = { "name_index": _(">H") }
            elif tag in (9, 10, 11):
                class_index, name_and_type_index  = _(">HH")
                constant_pool[x] = {
                    "class_index": class_index,
                    "name_and_type_index": name_and_type_index
                }
            elif tag == 8:
                constant_pool[x] = { "string_index": _(">H") }
            elif tag == 3:
                constant_pool[x] = { "value": _(">i") }
            elif tag == 4:
                constant_pool[x] = { "value": _(">f") }
            elif tag == 5:
                constant_pool[x] = { "value": _(">q") }
            elif tag == 6:
                constant_pool[x] = { "value": _(">d") }
            elif tag == 12:
                name_index, descriptor_index = _(">HH")
                constant_pool[x] = {
                    "name_index": name_index,
                    "descriptor_index": descriptor_index
                }
            elif tag == 1:
                length = _(">H")
                constant_pool[x] = { "value": _(">%ss" % length) }

            constant_pool[x]["tag"] = tag
            x += 2 if tag in (5,6) else 1

        for k,v in constant_pool.items():
            for k2, v2 in v.items():
                if k2.endswith("_index"):
                    constant_pool[k][k2[:-6]] = constant_pool[v2]

        self._constants = constant_pool

    @property
    def constants(self):
        if hasattr(self, "_constants"):
            return self._constants

        raise ClassError("class not loaded")

    @property
    def interfaces(self):
        if hasattr(self, "_interfaces"):
            return self._interfaces

        raise ClassError("class not loaded")

    @property
    def fields(self):
        if hasattr(self, "_fields"):
            return self._fields

        raise ClassError("class not loaded")

    @property
    def methods(self):
        if hasattr(self, "_methods"):
            return self._methods
        raise ClassError("class not loaded")

    @property
    def attributes(self):
        if hasattr(self, "_attributes"):
            return self._attributes

        raise ClassError("class not loaded")
        
    @property
    def is_public(self):
        return True if self.flags & 0x0001 else False

    @property
    def is_final(self):
        return True if self.flags & 0x0010 else False

    @property
    def is_super(self):
        return True if self.flags & 0x0020 else False

    @property
    def is_interface(self):
        return True if self.flags & 0x0200 else False

    @property
    def is_abstract(self):
        return True if self.flags & 0x0400 else False

    @property
    def is_synthetic(self):
        return True if self.flags & 0x1000 else False

    @property
    def is_annotation(self):
        return True if self.flags & 0x2000 else False

    @property
    def is_enum(self):
        return True if self.flags & 0x4000 else False

