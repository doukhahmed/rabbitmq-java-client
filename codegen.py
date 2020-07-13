#!/usr/bin/env python

## Copyright (c) 2007-2020 VMware, Inc. or its affiliates.  All rights reserved.
##
## This software, the RabbitMQ Java client library, is triple-licensed under the
## Mozilla Public License 2.0 ("MPL"), the GNU General Public License version 2
## ("GPL") and the Apache License version 2 ("ASL"). For the MPL, please see
## LICENSE-MPL-RabbitMQ. For the GPL, please see LICENSE-GPL2.  For the ASL,
## please see LICENSE-APACHE2.
##
## This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY KIND,
## either express or implied. See the LICENSE file for specific language governing
## rights and limitations of this software.
##
## If you have any questions regarding licensing, please contact us at
## info@rabbitmq.com.

from __future__ import nested_scopes
from __future__ import print_function

import re
import sys

from amqp_codegen import *

class BogusDefaultValue(Exception):
    def __init__(self, value):
        self.value = value
    def __str__(self):
        return repr(self.value)


def java_constant_name(c):
    return '_'.join(re.split('[- ]', c.upper()))

javaTypeMap = {
    'octet': 'int',
    'shortstr': 'String',
    'longstr': 'LongString',
    'short': 'int',
    'long': 'int',
    'longlong': 'long',
    'bit': 'boolean',
    'table': 'Map<String,Object>',
    'timestamp': 'Date'
    }

javaTypesToCheckForNull = set([
    'String',
    'LongString',
    'Date'
    ])

# the scalar types in the range of javaTypeMap must be in javaScalarTypes
javaScalarTypes = set([
    'int',
    'long',
    'boolean'
    ])
# the javaScalarTypes must be in the domain of javaBoxedTypeMap
javaBoxedTypeMap = {
    'int': 'Integer',
    'long': 'Long',
    'boolean': 'Boolean'
    }
def java_boxed_type(jtype):
    if jtype in javaScalarTypes:
        return javaBoxedTypeMap[jtype]
    else:
        return jtype

def java_type(spec, domain):
    return javaTypeMap[spec.resolveDomain(domain)]

def java_name(upperNext, name):
    out = ''
    for c in name:
        if not c.isalnum():
            upperNext = True
        elif upperNext:
            out += c.upper()
            upperNext = False
        else:
            out += c
    return out

def java_class_name(name):
    return java_name(True, name)

def java_getter_name(name):
    return java_name(False, 'get-' + name)

def java_field_name(name):
    return java_name(False, name)
def java_field_type(spec, domain):
    return javaTypeMap[spec.resolveDomain(domain)]

def java_field_default_value(jtype, value):
    if jtype == 'int':
        return value
    elif jtype == 'boolean':
        return ('%s'% (value)).lower()
    elif jtype == 'String':
        return '"%s"' % (value)
    elif jtype == 'LongString':
        return 'LongStringHelper.asLongString("%s")' % (value)
    elif jtype == 'long':
        return '%sL' % (value)
    elif jtype == 'Map<String,Object>':
        return "null"
    else:
        raise BogusDefaultValue("JSON provided default value %s for suspicious type %s" % (value, jtype))

def typeNameDefault(spec, a):
    fieldType = java_field_type(spec, a.domain)
    defaultVal = java_field_default_value(fieldType, a.defaultvalue)
    return (fieldType, java_field_name(a.name), defaultVal)

def nullCheckedFields(spec, m):
    fieldsToNullCheck = set([])
    for a in m.arguments:
        (jfType, jfName, jfDefault) = typeNameDefault(spec,a)
        if jfType in javaTypesToCheckForNull:
            fieldsToNullCheck.add(jfName)
    return fieldsToNullCheck

#---------------------------------------------------------------------------

def printFileHeader():
    print("""//   NOTE: This -*- java -*- source code is autogenerated from the AMQP
//         specification!
//
// Copyright (c) 2007-2020 VMware, Inc. or its affiliates.  All rights reserved.
//
// This software, the RabbitMQ Java client library, is triple-licensed under the
// Mozilla Public License 2.0 ("MPL"), the GNU General Public License version 2
// ("GPL") and the Apache License version 2 ("ASL"). For the MPL, please see
// LICENSE-MPL-RabbitMQ. For the GPL, please see LICENSE-GPL2.  For the ASL,
// please see LICENSE-APACHE2.
//
// This software is distributed on an "AS IS" basis, WITHOUT WARRANTY OF ANY KIND,
// either express or implied. See the LICENSE file for specific language governing
// rights and limitations of this software.
//
// If you have any questions regarding licensing, please contact us at
// info@rabbitmq.com.
//
""")

def genJavaApi(spec):
    def printHeader():
        printFileHeader()
        print("package com.rabbitmq.client;")
        print()
        print("import java.io.DataInputStream;")
        print("import java.io.IOException;")
        print("import java.util.Collections;")
        print("import java.util.HashMap;")
        print("import java.util.Map;")
        print("import java.util.Date;")
        print()
        print("import com.rabbitmq.client.impl.ContentHeaderPropertyWriter;")
        print("import com.rabbitmq.client.impl.ContentHeaderPropertyReader;")
        print("import com.rabbitmq.client.impl.LongStringHelper;")

    def printProtocolClass():
        print()
        print("    public static class PROTOCOL {")
        print("        public static final int MAJOR = %i;" % spec.major)
        print("        public static final int MINOR = %i;" % spec.minor)
        print("        public static final int REVISION = %i;" % spec.revision)
        print("        public static final int PORT = %i;" % spec.port)
        print("    }")

    def printConstants():
        print()
        for (c,v,cls) in spec.constants: print("    public static final int %s = %i;" % (java_constant_name(c), v))

    def builder(c,m):
        def ctorCall(c,m):
            ctor_call = "com.rabbitmq.client.impl.AMQImpl.%s.%s" % (java_class_name(c.name),java_class_name(m.name))
            ctor_arg_list = [ java_field_name(a.name) for a in m.arguments ]
            print("                    return new %s(%s);" % (ctor_call, ", ".join(ctor_arg_list)))

        def genFields(spec, m):
            for a in m.arguments:
                (jfType, jfName, jfDefault) = typeNameDefault(spec, a)
                if a.defaultvalue != None:
                    print("                private %s %s = %s;" % (jfType, jfName, jfDefault))
                else:
                    print("                private %s %s;" % (jfType, jfName))

        def genArgMethods(spec, m):
            for a in m.arguments:
                (jfType, jfName, jfDefault) = typeNameDefault(spec, a)

                print("                public Builder %s(%s %s)" % (jfName, jfType, jfName))
                print("                {   this.%s = %s; return this; }" % (jfName, jfName))

                if jfType == "boolean":
                    print("                public Builder %s()" % (jfName))
                    print("                {   return this.%s(true); }" % (jfName))
                elif jfType == "LongString":
                    print("                public Builder %s(String %s)" % (jfName, jfName))
                    print("                {   return this.%s(LongStringHelper.asLongString(%s)); }" % (jfName, jfName))

        def genBuildMethod(c,m):
            print("                public %s build() {" % (java_class_name(m.name)))
            ctorCall(c,m)
            print("                }")

        print()
        print("            // Builder for instances of %s.%s" % (java_class_name(c.name), java_class_name(m.name)))
        print("            public static final class Builder")
        print("            {")
        genFields(spec, m)
        print()
        print("                public Builder() { }")
        print()
        genArgMethods(spec, m)
        genBuildMethod(c,m)
        print("            }")

    def printClassInterfaces():
        for c in spec.classes:
            print()
            print("    public static class %s {" % (java_class_name(c.name)))
            for m in c.allMethods():
                print("        public interface %s extends Method {" % ((java_class_name(m.name))))
                for a in m.arguments:
                    print("            %s %s();" % (java_field_type(spec, a.domain), java_getter_name(a.name)))
                builder(c,m)
                print("        }")
            print("    }")

    def printReadProperties(c):
        if c.fields:
            for f in c.fields:
                print("            boolean %s_present = reader.readPresence();" % (java_field_name(f.name)))
            print()

        print("            reader.finishPresence();")

        if c.fields:
            print()
            for f in c.fields:
                (jfName, jfClass) = (java_field_name(f.name), java_class_name(f.domain))
                print("            this.%s = %s_present ? reader.read%s() : null;" % (jfName, jfName, jfClass))

    def printWritePropertiesTo(c):
        print()
        print("        public void writePropertiesTo(ContentHeaderPropertyWriter writer)")
        print("            throws IOException")
        print("        {")
        if c.fields:
            for f in c.fields:
                print("            writer.writePresence(this.%s != null);" % (java_field_name(f.name)))
            print()
        print("            writer.finishPresence();")
        if c.fields:
            print()
            for f in c.fields:
                (jfName, jfClass) = (java_field_name(f.name), java_class_name(f.domain))
                print("            if (this.%s != null) writer.write%s(this.%s);" % (jfName, jfClass, jfName))
        print("        }")

    def printAppendPropertyDebugStringTo(c):
        appendList = [ "%s=\")\n               .append(this.%s)\n               .append(\""
                       % (f.name, java_field_name(f.name))
                       for f in c.fields ]
        print()
        print("        public void appendPropertyDebugStringTo(StringBuilder acc) {")
        print("            acc.append(\"(%s)\");" % (", ".join(appendList)))
        print("        }")

    def printPropertiesBuilderClass(c):
        def printBuilderSetter(fieldType, fieldName):
            print("            public Builder %s(%s %s)" % (fieldName, java_boxed_type(fieldType), fieldName))
            print("            {   this.%s = %s; return this; }" % (fieldName, fieldName))
            if fieldType == "boolean":
                print("            public Builder %s()" % (fieldName))
                print("            {   return this.%s(true); }" % (fieldName))
            elif fieldType == "LongString":
                print("            public Builder %s(String %s)" % (fieldName, fieldName))
                print("            {   return this.%s(LongStringHelper.asLongString(%s)); }" % (fieldName, fieldName))

        print()
        print("        public static final class Builder {")
        # fields
        for f in c.fields:
            (fType, fName) = (java_field_type(spec, f.domain), java_field_name(f.name))
            print("            private %s %s;" % (java_boxed_type(fType), fName))
        # ctor
        print()
        print("            public Builder() {};")
        # setters
        print()
        for f in c.fields:
            printBuilderSetter(java_field_type(spec, f.domain), java_field_name(f.name))
        print()
        jClassName = java_class_name(c.name)
        # build()
        objName = "%sProperties" % (jClassName)
        ctor_parm_list = [ java_field_name(f.name) for f in c.fields ]
        print("            public %s build() {" % (objName))
        print("                return new %s" % (objName))
        print("                    ( %s" % ("\n                    , ".join(ctor_parm_list)))
        print("                    );")
        print("            }")

        print("        }")

    def printPropertiesBuilder(c):
        print()
        print("        public Builder builder() {")
        print("            Builder builder = new Builder()")
        setFieldList = [ "%s(%s)" % (fn, fn)
                         for fn in [ java_field_name(f.name) for f in c.fields ]
                         ]
        print("                .%s;" % ("\n                .".join(setFieldList)))
        print("            return builder;")
        print("        }")

    def printPropertiesClass(c):
        def printGetter(fieldType, fieldName):
            capFieldName = fieldName[0].upper() + fieldName[1:]
            print("        public %s get%s() { return this.%s; }" % (java_boxed_type(fieldType), capFieldName, fieldName))

        jClassName = java_class_name(c.name)

        print()
        print("    public static class %sProperties extends com.rabbitmq.client.impl.AMQ%sProperties {" % (jClassName, jClassName))
        #property fields
        for f in c.fields:
            (fType, fName) = (java_boxed_type(java_field_type(spec, f.domain)), java_field_name(f.name))
            print("        private %s %s;" % (fType, fName))

        #explicit constructor
        if c.fields:
            print()
            consParmList = [ "%s %s" % (java_boxed_type(java_field_type(spec,f.domain)), java_field_name(f.name))
                             for f in c.fields ]
            print("        public %sProperties(" % (jClassName))
            print("            %s)" % (",\n            ".join(consParmList)))
            print("        {")
            for f in c.fields:
                (fType, fName) = (java_field_type(spec, f.domain), java_field_name(f.name))
                if fType == "Map<String,Object>":
                    print("            this.%s = %s==null ? null : Collections.unmodifiableMap(new HashMap<String,Object>(%s));" % (fName, fName, fName))
                else:
                    print("            this.%s = %s;" % (fName, fName))
            print("        }")

        #datainputstream constructor
        print()
        print("        public %sProperties(DataInputStream in) throws IOException {" % (jClassName))
        print("            super(in);")
        print("            ContentHeaderPropertyReader reader = new ContentHeaderPropertyReader(in);")

        printReadProperties(c)

        print("        }")

        # default constructor
        print("        public %sProperties() {}" % (jClassName))

        #class properties
        print("        public int getClassId() { return %i; }" % (c.index))
        print("        public String getClassName() { return \"%s\"; }" % (c.name))

        if c.fields:
            equalsHashCode(spec, c.fields, java_class_name(c.name), 'Properties', False)

        printPropertiesBuilder(c)

        #accessor methods
        print()
        for f in c.fields:
            (jType, jName) = (java_field_type(spec, f.domain), java_field_name(f.name))
            printGetter(jType, jName)

        printWritePropertiesTo(c)
        printAppendPropertyDebugStringTo(c)
        printPropertiesBuilderClass(c)

        print("    }")

    def printPropertiesClasses():
        for c in spec.classes:
            if c.hasContentProperties:
                printPropertiesClass(c)

    printHeader()
    print()
    print("public interface AMQP {")

    printProtocolClass()
    printConstants()
    printClassInterfaces()
    printPropertiesClasses()

    print("}")

#--------------------------------------------------------------------------------

def equalsHashCode(spec, fields, jClassName, classSuffix, usePrimitiveType):
        print()
        print()
        print("        @Override")
        print("        public boolean equals(Object o) {")
        print("            if (this == o)")
        print("                return true;")
        print("            if (o == null || getClass() != o.getClass())")
        print("               return false;")
        print("            %s%s that = (%s%s) o;" % (jClassName, classSuffix, jClassName, classSuffix))

        for f in fields:
            (fType, fName) = (java_field_type(spec, f.domain), java_field_name(f.name))
            if usePrimitiveType and fType in javaScalarTypes:
                print("            if (%s != that.%s)" % (fName, fName))
            else:
                print("            if (%s != null ? !%s.equals(that.%s) : that.%s != null)" % (fName, fName, fName, fName))

            print("                return false;")

        print("            return true;")
        print("        }")

        print()
        print("        @Override")
        print("        public int hashCode() {")
        print("            int result = 0;")

        for f in fields:
            (fType, fName) = (java_field_type(spec, f.domain), java_field_name(f.name))
            if usePrimitiveType and fType in javaScalarTypes:
                if fType == 'boolean':
                    print("            result = 31 * result + (%s ? 1 : 0);" % fName)
                elif fType == 'long':
                    print("            result = 31 * result + (int) (%s ^ (%s >>> 32));" % (fName, fName))
                else:
                    print("            result = 31 * result + %s;" % fName)
            else:
                print("            result = 31 * result + (%s != null ? %s.hashCode() : 0);" % (fName, fName))

        print("            return result;")
        print("        }")

def genJavaImpl(spec):
    def printHeader():
        printFileHeader()
        print("package com.rabbitmq.client.impl;")
        print()
        print("import java.io.IOException;")
        print("import java.io.DataInputStream;")
        print("import java.util.Collections;")
        print("import java.util.HashMap;")
        print("import java.util.Map;")
        print()
        print("import com.rabbitmq.client.AMQP;")
        print("import com.rabbitmq.client.LongString;")
        print("import com.rabbitmq.client.UnknownClassOrMethodId;")
        print("import com.rabbitmq.client.UnexpectedMethodError;")

    def printClassMethods(spec, c):
        print()
        print("    public static class %s {" % (java_class_name(c.name)))
        print("        public static final int INDEX = %s;" % (c.index))
        for m in c.allMethods():

            def getters():
                if m.arguments:
                    print()
                    for a in m.arguments:
                        print("            public %s %s() { return %s; }" % (java_field_type(spec,a.domain), java_getter_name(a.name), java_field_name(a.name)))

            def constructors():
                print()
                argList = [ "%s %s" % (java_field_type(spec,a.domain),java_field_name(a.name)) for a in m.arguments ]
                print("            public %s(%s) {" % (java_class_name(m.name), ", ".join(argList)))

                fieldsToNullCheckInCons = [f for f in nullCheckedFields(spec, m)]
                fieldsToNullCheckInCons.sort()

                for f in fieldsToNullCheckInCons:
                    print("                if (%s == null)" % (f))
                    print("                    throw new IllegalStateException(\"Invalid configuration: '%s' must be non-null.\");" % (f))

                for a in m.arguments:
                    (jfType, jfName) = (java_field_type(spec, a.domain), java_field_name(a.name))
                    if jfType == "Map<String,Object>":
                        print("                this.%s = %s==null ? null : Collections.unmodifiableMap(new HashMap<String,Object>(%s));" % (jfName, jfName, jfName))
                    else:
                        print("                this.%s = %s;" % (jfName, jfName))

                print("            }")

                consArgs = [ "rdr.read%s()" % (java_class_name(spec.resolveDomain(a.domain))) for a in m.arguments ]
                print("            public %s(MethodArgumentReader rdr) throws IOException {" % (java_class_name(m.name)))
                print("                this(%s);" % (", ".join(consArgs)))
                print("            }")

            def others():
                print()
                print("            public int protocolClassId() { return %s; }" % (c.index))
                print("            public int protocolMethodId() { return %s; }" % (m.index))
                print("            public String protocolMethodName() { return \"%s.%s\";}" % (c.name, m.name))
                print()
                print("            public boolean hasContent() { return %s; }" % (trueOrFalse(m.hasContent)))
                print()
                print("            public Object visit(MethodVisitor visitor) throws IOException")
                print("            {   return visitor.visit(this); }")

            def trueOrFalse(truthVal):
                if truthVal:
                    return "true"
                else:
                    return "false"

            def argument_debug_string():
                appendList = [ "%s=\")\n                   .append(this.%s)\n                   .append(\""
                               % (a.name, java_field_name(a.name))
                               for a in m.arguments ]
                print()
                print("            public void appendArgumentDebugStringTo(StringBuilder acc) {")
                print("                acc.append(\"(%s)\");" % ", ".join(appendList))
                print("            }")

            def write_arguments():
                print()
                print("            public void writeArgumentsTo(MethodArgumentWriter writer)")
                print("                throws IOException")
                print("            {")
                for a in m.arguments:
                    print("                writer.write%s(this.%s);" % (java_class_name(spec.resolveDomain(a.domain)), java_field_name(a.name)))
                print("            }")

            #start
            print()
            print("        public static class %s" % (java_class_name(m.name),))
            print("            extends Method")
            print("            implements com.rabbitmq.client.AMQP.%s.%s" % (java_class_name(c.name), java_class_name(m.name)))
            print("        {")
            print("            public static final int INDEX = %s;" % (m.index))
            print()
            for a in m.arguments:
                print("            private final %s %s;" % (java_field_type(spec, a.domain), java_field_name(a.name)))

            getters()
            constructors()
            others()
            if m.arguments:
                equalsHashCode(spec, m.arguments, java_class_name(m.name), '', True)

            argument_debug_string()
            write_arguments()

            print("        }")
        print("    }")

    def printMethodVisitor():
        print()
        print("    public interface MethodVisitor {")
        for c in spec.allClasses():
            for m in c.allMethods():
                print("        Object visit(%s.%s x) throws IOException;" % (java_class_name(c.name), java_class_name(m.name)))
        print("    }")

        #default method visitor
        print()
        print("    public static class DefaultMethodVisitor implements MethodVisitor {")
        for c in spec.allClasses():
            for m in c.allMethods():
               print("        public Object visit(%s.%s x) throws IOException { throw new UnexpectedMethodError(x); }" % (java_class_name(c.name), java_class_name(m.name)))
        print("    }")

    def printMethodArgumentReader():
        print()
        print("    public static Method readMethodFrom(DataInputStream in) throws IOException {")
        print("        int classId = in.readShort();")
        print("        int methodId = in.readShort();")
        print("        switch (classId) {")
        for c in spec.allClasses():
            print("            case %s:" % (c.index))
            print("                switch (methodId) {")
            for m in c.allMethods():
                fq_name = java_class_name(c.name) + '.' + java_class_name(m.name)
                print("                    case %s: {" % (m.index))
                print("                        return new %s(new MethodArgumentReader(new ValueReader(in)));" % (fq_name))
                print("                    }")
            print("                    default: break;")
            print("                } break;")
        print("        }")
        print()
        print("        throw new UnknownClassOrMethodId(classId, methodId);")
        print("    }")

    def printContentHeaderReader():
        print()
        print("    public static AMQContentHeader readContentHeaderFrom(DataInputStream in) throws IOException {")
        print("        int classId = in.readShort();")
        print("        switch (classId) {")
        for c in spec.allClasses():
            if c.fields:
                print("            case %s: return new %sProperties(in);" %(c.index, (java_class_name(c.name))))
        print("            default: break;")
        print("        }")
        print()
        print("        throw new UnknownClassOrMethodId(classId);")
        print("    }")

    printHeader()
    print()
    print("public class AMQImpl implements AMQP {")

    for c in spec.allClasses(): printClassMethods(spec,c)

    printMethodVisitor()
    printMethodArgumentReader()
    printContentHeaderReader()

    print("}")

#--------------------------------------------------------------------------------

def generateJavaApi(specPath):
    genJavaApi(AmqpSpec(specPath))

def generateJavaImpl(specPath):
    genJavaImpl(AmqpSpec(specPath))

if __name__ == "__main__":
    do_main(generateJavaApi, generateJavaImpl)
