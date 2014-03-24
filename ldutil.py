#!/usr/bin/python

#
# ldutil helps you to manage library dependencies on a filesystem  
#
# Copyright (C) 2014  Ilario Pittau (ilariopittau[at]gmail[dot]com)
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
#

import getopt, sys, subprocess, os, fnmatch, pickle, re, hashlib
from stat import *


def usage():
    print "Usage: ldutil [-p <pickle_file>] [-o <output_file>] [-i <input_file> [c <check_file>] [s <search_file>]] [d <search_dir>] [vnml] [h]"
    print " -o output_file : recurse the search_dir for reverse tree and write the tree in the file"
    print " -p pickle_file : use pickle function to dump the lib_list dependency tree"
    print " -i input_file  : use the input_file as tree for the binaries, the file must be generated with the pickle feature"
    print " -c check_file  : print the list of libs that needs check_file"
    print " -s search_file : print all occurences of search_file"
    print " -d search_dir  : use this dir as base for find and recurse"
    print " -n             : print all binaries that nobody use"
    print " -m             : print all binaries that have a unsatisfied dependency"
    print " -l             : manage symbolic links (EXPERIMENTAL)"
    print " -v             : verbose_flag mode on"
    print "Examples:"
    print " ldutil -d /usr/lib -p /tmp/pickle"
    print " ldutil -d /usr/lib -i /tmp/pickle -s libc.so"
    print " ldutil -d /usr/lib -i /tmp/pickle -n"
    

 

#Search a lib starting from search_dir
#@param filename: the file to search on the search_dir
#@param search_dir: the directory to use as root
#@param link_enable_flag: if true returns the link otherwise the linked file
#@return the file if founded, the linked file if flag is False, an empty string if not founded
def findout(filename, search_dir, link_enable_flag=False):
  #print "finding " + filename + "..."
  
  find_list = []
  for root, dirs, files in os.walk(search_dir):
    for basename in fnmatch.filter(files, filename):
      found_lib = os.path.join(root, basename)
      mode = os.lstat(found_lib).st_mode
      if (link_enable_flag == False):
        if S_ISLNK(mode):
          refound = os.path.dirname(found_lib) +"/"+ os.readlink(found_lib)
          #print "found " + filename + " -> " + refound
          return refound
      #print "found " + found_lib
      return found_lib
      
  return ""

#Function that analyze a binary and its dependencies recursively
#@param current: file to be analyzed, uses readelf -d to check dependecies, current is fullpath
#@param father: needed for the recursive step, is the father. father is "nobody" for the first step
#@return the list of dependencies of the current binary
def analyze(current, father):

    #print "analyze " + current
    
    lib_basename = os.path.basename(current)
        
    if lib_basename in lib_list:
      return []
    
    lib_list[lib_basename] = []

    #readelf regExp
    re_readelf = re.compile('\(NEEDED\)[\s]+[A-Za-z\s]+: \[(.+)\]')
    
    try:
        readelf_output = subprocess.check_output("readelf -d "+current,stderr=subprocess.STDOUT,shell=True) 
    except subprocess.CalledProcessError, err: 
        #print "readelf error " + current
        lib_list.pop(lib_basename)
        return []
        
    #print "analyzed " + current
    
    #parse the output of the readelf command
    sub_lib_list = re_readelf.findall(readelf_output)
    
    #print str(len(sub_lib_list))
                
    #analize the used libraries
    for sub_lib in sub_lib_list:
        #The lib has been already analyzed, we add it and its dependencies
        if sub_lib in lib_list:
          lib_list[lib_basename].append(sub_lib)
          lib_list[lib_basename] += lib_list[sub_lib]
        else:
          #Search if the dependency is satisfied
          found_lib = findout(sub_lib, search_dir);
          
          #if yes add the lib and all dependencies calling a recursive step
          if (found_lib != ""):
              lib_list[lib_basename].append(os.path.basename(found_lib))
              lib_list[lib_basename] += analyze(found_lib, current)
              
          #otherwise write that the dependency is unsatisfied ("miss" + name of the lib)
          else:
              #print sub_lib + " miss for " + lib_basename
              lib_list[lib_basename].append("miss " + sub_lib)
            
    #print lib_list[lib_basename]
    
    #this is useful to remove duplicates
    lib_list[lib_basename] = list(set(lib_list[lib_basename]))
    return lib_list[lib_basename]

#function that go deep on the directory and call ther recursive function analyze for each binary
#prints a dot for each file analyzed
#@param research_dir: directory to use as start point
def create_dependency_tree(research_dir):
    #print subprocess.check_output("find "+search_dir, shell=True)

    print "going.. " + research_dir
    total_file_num = 0
    file_num = 0
    for root, dirs, files in os.walk(research_dir):
        for new_file in files:
          total_file_num = total_file_num + 1 
  
    for root, dirs, files in os.walk(research_dir):
        #Analyze only files, not links
        for new_file in files:
          file_num = file_num + 1 
          print ("Analyze " + str(file_num) +"/"+ str(total_file_num) ) 
          sys.stdout.write("\033[F")
          pathname = os.path.join(root, new_file)
          mode = os.lstat(pathname).st_mode
          #links are skipped
          if S_ISLNK(mode): 
              #print "link " + pathname + " " + str(mode)
              pass
          elif S_ISREG(mode):
              # It's a file, call the recursive function to analyze it
              #print "analyze " + pathname            
              analyze(pathname, "nobody")
          else:
              # Unknown file type, print a message
              print 'Skipping %s' % pathname
              pass


#Function to calculate the reverse tree starting from the dependency list
def reverse_analysis():
  for lib in lib_list.keys():
    #Add the lib to reverse_lib_list if it's not present
    if lib not in reverse_lib_list:
      reverse_lib_list[lib] = []
    
    for father_lib in lib_list.keys():
      if lib in lib_list[father_lib]:
        reverse_lib_list[lib].append(father_lib)


def link_managment():
  print "Duplicate libs"
  
  for lib in lib_list.keys():
    lib_found = findout(lib, search_dir, True)
    if re.match('.+\.so.+',lib):#if is a lib
      #filename = os.path.splitext(lib)
      lib_no_version = lib.split(".so.")[0] + ".so"
      for num_version in lib.split(".so.")[1].split("."):
        fullname_lib_no_version = os.path.join(os.path.dirname(lib_found), lib_no_version)
        #lib_no_version_found = findout(lib_no_version, search_dir, True)
        print "Tring... " + fullname_lib_no_version
        if not os.path.exists(fullname_lib_no_version) or not S_ISLNK(os.lstat(fullname_lib_no_version).st_mode):
            print lib_no_version + " -> " +  lib_found + " ?"
            if os.path.exists(fullname_lib_no_version):
              print fullname_lib_no_version + " exist, do you want replace it with the symlink?"
            else: 
              print fullname_lib_no_version + " not exist, do you want create a new the symlink?"
            response = raw_input()
            if response == "y" : 
              print "create: " + fullname_lib_no_version
              os.symlink(lib, fullname_lib_no_version)
            else:
              print "pass..."
        else:
          print fullname_lib_no_version + " link exist!"
              
        lib_no_version += "." + num_version  



#Main (this is the point where the program start)
try:
    opts, args = getopt.getopt(sys.argv[1:], "hi:vc:nd:s:o:p:ml", ["input="])
except getopt.GetoptError, err:
    print "error"
    # print help information and exit:
    print str(err) # will print something like "option -a not recognized"
    usage()
    sys.exit(2)
    
#variable initialization
#input file prepared with the dependency tree
input_file = ""
#if enabled prints a lot of debug
verbose_flag = False
#if enabled print libs that nobody uses
nobody_flag = False
#if enabled print libs that have unsatisfied dependency
miss_flag = False
#if enabled start the interactive managment of symbolic links"
link_flag = False
#print the list of libs that needs check_file
check_file = ""
#Print lib_list and reverse_lib_list
print_all=False

#default fs directory to scan
search_dir="/tmp/asd"
#used to print all occurrences of the lib
search_file=""
#file output with the filter output
output_file=""
#file output with the prescanned dependency tree
pickle_file=""

try:

  #option parsing
  for o, a in opts:
      if o == "-v":
          verbose_flag = True
      elif o in ("-h", "--help"):
          usage()
          sys.exit(0)
      elif o in ("-i", "--input"):
          input_file = a
      elif o in ("-o", "--output"):
          output_file = a
      elif o in ("-c"):
          check_file = a
      elif o in ("-n"):
          nobody_flag = True
      elif o in ("-d"):
          search_dir = a
      elif o in ("-s"):
          search_file = a
      elif o in ("-p"):
          pickle_file = a
      elif o in ("-m"):
          miss_flag = True
      elif o in ("-l"):
          link_flag = True
      else:
          assert False, "unhandled option"


  #Contains all libs on the system and their dependencies
  lib_list = dict()

  #Contains all libs on the system and the bins/libs that depend on it
  reverse_lib_list=dict()

  #If the output file is set, create the dependency tree
  if input_file == "":
    create_dependency_tree(search_dir)
  else:
  #otherwise open the pickle file and load the lib_list
    input_fd = open(input_file,"rb");
    lib_list = pickle.load(input_fd);
    input_fd.close()
    
  #Open the pickle file and dump the list on it then exit
  if pickle_file != "":
    pickle_fd = open(pickle_file,"wb");
    pickle.dump(lib_list,pickle_fd);
    pickle_fd.close()
    print ""
    sys.exit(0)


  #Perform the reverse analysis after the scan of the folder
  reverse_analysis()

  #Output file is used to save the output of the request feature
  if output_file != "" :
    output_fd = open(output_file, "w")

  #MAIN SWITCH over the implemented features
  #link managment is EXPERIMENTAL
  if (link_flag == True):
    link_managment()
  elif( check_file != ""):
  #Prints the bins that uses che check_file  
    if (check_file in reverse_lib_list):
      #Print the checkfile full name path
      print "This is the list of binaries that are using " + findout(check_file, search_dir)
      #Print every lib in its reverse list
      for lib in reverse_lib_list[check_file]:
        if output_file != "" :
          output_fd.write(findout(k, search_dir) + "\n")  
        print "   " + findout(lib, search_dir)
    else:
      print "not found"
  elif (nobody_flag):
  #Prints the library that nobody is using and theoretically could be deleted
    print "This is the list of libraries (.so) that nobody uses:"
    for k, v in reverse_lib_list.iteritems():
      if len(reverse_lib_list[k]) == 0 :
        #print only the .so files
        if re.match('.+\.so*',k):
          if output_file != "" :
            output_fd.write(findout(k, search_dir) + "\n")
            
          lib_found = findout(k, search_dir)
          if lib_found == "":
            print k + " not found!"
          else:
            print lib_found
  elif (search_file):
  #Prints each occurence of the searched file
    for lib_filter in fnmatch.filter(lib_list, "*"+search_file+"*"):
      search_file_found = findout(lib_filter, search_dir)
      print "###################################################################"
      if S_ISLNK(os.lstat(search_file_found).st_mode):
        print search_file_found + " is a link"
      else:
        print search_file_found + " is not a link"
      print lib_filter + " is used by:"
      print reverse_lib_list[lib_filter]
      print lib_filter + " uses:"
      print lib_list[lib_filter]
  elif (miss_flag):
  #Print a missing dependecy
    for k, v in lib_list.iteritems():
      for basename in fnmatch.filter(lib_list[k], "miss*"):
        print k + " " + basename
  elif (print_all):
  #Print the list and reverse list
    for k, v in lib_list.iteritems():
      print k
      print v

    print "###################"

    for k, v in reverse_lib_list.iteritems():
      print k
      print v

except KeyboardInterrupt:
  print "Byee!"

#Close the file
if output_file != "" :
  output_fd.close()
