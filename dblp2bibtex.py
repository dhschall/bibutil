#!/usr/bin/env python3
# -*- coding: latin-1 -*-

####
####  bibcloud.py
####  v. 2016-08-01

# Copyright 2015-16 Ecole Polytechnique Federale Lausanne (EPFL)
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

####
####  This is a utility to download bibtex references from DBLP. It is based on
####  the original bibcloud.py script from EPFL, but significantly modified.
####  The script fetches bibtex references from DBLP using the DBLP key or DOI.
####  It can also fetch references from a list of aliases or from a .aux file.




import sys
import os
import xml.etree.ElementTree as ET
import subprocess
import time
import locale
import requests
import re
import yaml


import argparse

def parse_arguments():
    parser = argparse.ArgumentParser(description=
    """
    Bibtex utility tool (bibutil).
    Downloads bibtex references from DBLP library.
    As inputs DBLP reference keys or doi are accepted. Alternatively, an entire
    file of aliases can be provided to be fetched from DBLP.
    """)
    parser.add_argument("keys", type = str, nargs='*',
                        help = "DBLP or doi keys. DBLP must start with DBLP:<key>")

    parser.add_argument("--aliasfile", "-a", type=str,
                        help="Provide a yaml file with aliases key pairs. "
                            "'<alias>: DBLP:<key>' or '<alias> <doi>'")
    parser.add_argument("--bibcloud", "-ba", type=str,
                        help="Provide an old fashion bibcloud alias file "
                            "'<alias> DBLP:<key>' or '<alias> DOI:<doi>' or '<alias> <doi>'.")
    parser.add_argument("--aux", type=str,
                        help="Point to the .aux file of your latex project. "
                        "The file will be used to filter your alias file and fetches only "
                        "citations used in the project.")
    parser.add_argument("--output", "-o", type=str, default="DBLP.bib")

    return parser.parse_args()





DEBUG = 0

gBibStyle = ""

############
### globals
############

ALIAS = {}
REVALIAS = {}
# TITLESUB = {}

# Function to print red text
def red(text):
    return "\033[91m" + text + "\033[0m"

##### extraction from bibtex .aux file #########
def find_citation(l):
    x = l.find("\\citation{")
    if (x>=0):
        y = l.find("{")
        z = l.find("}",y)
        return l[y+1:z]

    x = l.find("\\abx@aux@cite{")
    if (x>=0):
        y = l.find("{")
        z = l.find("}",y)
        return l[y+1:z]

    return ""

def load_references(bibname):

    global gBibStyle

    if not os.path.isfile(bibname) and not os.path.isfile(bibname+".aux"):
        print("FATAL -- File "+bibname+" does not exist")
        sys.exit(1)

    print("bibcloud: parsing ",bibname)
    lines = [line.strip() for line in open(bibname)]

    BibSyle = ""
    bibstyleline = [x for x in lines if x.find("\\bibstyle")>=0]
    print("BIBSTYLE is ",bibstyleline)
    if len(bibstyleline)==1:
        x = bibstyleline[0].split("{")
        x = x[1].split("}")
        gBibStyle = x[0]
        print("BIBSTYLE (stipped)",gBibStyle)


    lines =  [find_citation(line) for line in lines]
    lines  = [c.strip(" ") for c in lines if c != ""]
    lines =  [c.split(",") for c in lines]
    lines =  [y for x in lines for y in x]

    return  sorted(set(lines))


####### strip_comments

def strip_comment(l):
    pos = l.find("%")
    if pos >=0:
        return  l[:pos]
    else:
        return l

def validate_bib(tmp):
    if tmp[0] == "@" and tmp[-3] == "}":
        return True
    return False

urls = {
    "DBLP" : "https://dblp.uni-trier.de/rec",
    "DOI"  : "https://dblp.org/doi",
}

####### Download ###########
def download_dblp(label):
    # Process
    dblp = False
    ret = None
    err = ""
    key = label

    if "DBLP:" in label:
        key = label[5:]
        dblp = True

    elif "DOI:" in label:
        key = label[4:]


    try:
        # Fetch bib
        _url = f"{urls['DBLP'] if dblp else urls['DOI']}/{key}.bib"
        bib = requests.get(_url).text

        err = f"ERROR key: {key}, url: {_url}"
        # validate
        if not validate_bib(bib):
            return None, err
        ret = bib

    except KeyboardInterrupt:
        # quit
        sys.exit()
    except:
        print(f"ERROR cannot fetch {key}")

    # Ret the cite key in the bib entry
    # If aliased key is found, replace it
    if ret:
        rep = label
        if label in REVALIAS:
            rep = REVALIAS[label]

        print(f"Replace {label} with {rep}")
        ret = re.sub('{.+,', '{' + rep + ',', bib, count=1)

    return ret, err






def download_doi(key):
    # Processing DBLP keys
    ret = None
    try:
        bib = requests.get(f"https://dblp.org/doi/{key}.bib").text
        bib = re.sub('{DBLP.*,', '{' + REVALIAS[key] + ',', bib)
        ret = bib
    except KeyboardInterrupt:
        # quit
        sys.exit()
    except:
        print(f"ERROR cannot fetch {key}")

    return ret


def download_refs(citations):
    fetch_data = []
    success = 0
    # import logging
    # logging.basicConfig(level=logging.DEBUG)

    for i, c in enumerate(citations):
        bib, err = download_dblp(c)
        print(f"Fetch {i}/{len(citations)}: key: {c} -> {'Success' if bib else red('Failed')} {'' if bib else ' > ' + err }")
        if bib:
            fetch_data += [bib]
            success+=1

    return fetch_data, success

# ########## html_to_bibtex ######
# ### brutal escaping

# HTML_TO_BIB = {
#     u'�' : "{\\'e}",
#     u'�' : "{\\\"o}",
#     u'�' : "{\\\"a}",
#     u'�' : "{\\'E}",
#     u'�' : "{\\\"u}",
#     u"�" : "{\\'e}",
#     u"�" : "{\\`e}",
#     u"�" : "{\\'a}",
#     u"�" : "\\c{c}",
#     u"�" : "{\\\"O}",
#     u"�" : "\\'{\\i}",
#     u"�" : "{\\~{n}}",
#     u"�" : "{\\aa}",
#     u"�" : "{\\'y}",
#     u"\u2248" : "{$\\approx$}",
#     u"\u03BC" : "{$\\upmu{}$\\xspace}"

# }


# def author_trim(a):
#     x = a.split(' ')
#     lastword = x[len(x)-1]
#     if (lastword[0:2] == '00'):
# #        print("AUTHOR TRIM",x,lastword)
#         b =  ' '.join(x[0:len(x)-1])
# #        print("AUTHOR2 ",b)
#         return b
#     else:
#         return a


# def html_to_bibtex2(h):

#     try:
#         return str(h)
#     except:
#         print("DEBUG: HTML conversion ",h.encode('utf-8'))
#         x = ""
#         for c in h:
#             c2 = c.encode('utf-8')
#             if c in HTML_TO_BIB:
#                 x = x + HTML_TO_BIB[c]
#             else:
#                 x = x + c
#         print("DEBUG: HTML conversion ",h.encode('utf-8')," --> ",x.encode('utf-8'))
#         return x.encode('utf-8')


# def html_to_bibtex(s):
#     x = html_to_bibtex2(s)
#     x = x.replace("&","{\&}")
#     return x


# def escape_percent(s):
#     x = s.find("%")
#     if x>=0:
#         s2 = s[:x] + "\%" + escape_percent(s[x+1:])
#         print("ESCAPING%: ",s,s2)
#         return s2
#     else:
#         return s


# #complete mess
# def escape_percent_amp(s):

#     y = s.find("\\&")
#     if y>=0:
#         print("ESCAPING - skip \\&:",s )
#         return s[:y+2] + escape_percent_amp(s[y+2:])

#     x = s.find("%")
#     y = s.find("&")

#     if x>=0 and (x<y or y<0):
#         s2 = s[:x] + "\%" + escape_percent_amp(s[x+1:])
#         print("ESCAPING%: ",s,s2)
#         return s2
#     elif y>=0:
#         s2 = s[:y] + "\&" + escape_percent_amp(s[y+1:])
#         print("ESCAPING&: ",s,s2)
#         return s2
#     else:
#         return s


# DOI_IN_DBLP = ["http://doi.acm.org/","http://doi.ieeecomputersociety.org/","http://dx.doi.org/"]


# # warning - can have duplicate tags
# def output_doi_ee(url):

#     doi = url
#     for x in DOI_IN_DBLP:
#         doi = doi.replace(x,"")

# #    r = "   url = {"+url+"},\n"
#     r =""
#     if doi == url:
#         #print("DOI: ",url)
#         return r+"  "+"ee = {"+escape_percent(url)+"},\n"
#     else:
#         return r+"  "+"doi = {"+doi+"},\n"



###################################################
#################### main  ########################
###################################################
# process bib file from ARVG


latex_citations = []

args = parse_arguments()

if len(args.keys) == 0 and not args.aliasfile and not args.bibcloud:
    print("ERROR: a list of keys or an alias file must be provided.")
    exit(1)

if args.aux:
    latex_citations = load_references(args.aux)
    print(f"Found {len(latex_citations)} in {args.aux}")


if len(args.keys) > 0:
    latex_citations = args.keys



if args.bibcloud:

    with open(args.bibcloud, "r") as f:
        lines = [line.strip() for line in f]
        lines = [strip_comment(line) for line in lines]

    for l in lines:
        x = l.split()
        if len(x)>=2 and (x[1].find("DBLP:")>=0 or x[1].find("DOI:")>=0):
            #print("found alias ",x[0],x[1])
            ALIAS[x[0]] = x[1]
            REVALIAS[x[1]] = x[0]
            # if "DBLP" in x[1]:
            #     REVALIAS[x[1][5:]] = x[0]
            # if "DOI" in x[1]:
            #     REVALIAS[x[1][4:]] = x[0]

        elif len(x)>0:
            print("Alias parsing - bad line : ",x)

if args.aliasfile:
    data = yaml.load(open(args.aliasfile, "r"), Loader=yaml.FullLoader)
    for alias, key in data["aliases"].items():
        ALIAS[alias] = key
        REVALIAS[key] = alias
        if "DBLP" in key:
            REVALIAS[key[5:]] = alias


if len(latex_citations) == 0:
    print(f"No .aux file given. Download all {len(ALIAS)} references instead.")
    dblp_citations = ALIAS.values()
else:
    dblp_citations = [ALIAS[c] if c in ALIAS else c for c in latex_citations]



# print(dblp_citations)
data, successes = download_refs(dblp_citations)

print(f"Downloaded {len(data)} references.")

with open(args.output, "w") as f:
    print("Write references to " + args.output)
    f.writelines(data)


