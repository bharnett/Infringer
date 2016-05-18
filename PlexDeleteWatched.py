#!/usr/bin/python
####################################################################################
##                                  INFORMATION
####################################################################################
##   Developed by: Steven Johnson
##
##   Last Updated: 11/13/2013 4:00AM PST
##   
##   Description: Auto-Delete Watched Items In Plex
##
##   Required Configurations:
##      - PC       (Blank = AutoDetect  |  W = Windows  |  L = Linux/Unix/MAC )
##      - Host     (Hostname or IP  | Blank = 127.0.0.1)
##      - Port     (Port  |  Blank = 32400)
##      - Section  (Section aka Library 1 2 3 varies on your system  |  Blank = 1)
##      - Delete   (1 = Delete  |  Blank = 0 (For Testing or Review))
##      - Shows    ( ["Show1","Show2"]; = Kept Shows OR [""]; = DEL ALL SHOWS )
##      - OnDeck   ( 1 = Keep If On Deck  |  Blank = Delete Regardless if onDeck  )
##
####################################################################################
####################################################################################

PC = "L";
Host = "192.168.1.12";
Port = "";
Section = "6";
Delete = "0";
Shows = ["The Simpsons"];
OnDeck = "1";

####################################################################################
##                        NO NEED TO EDIT BELOW THIS LINE  
####################################################################################
import os
import xml.dom.minidom
import platform
import re

####################################################################################
##  Checking URL
####################################################################################
if Host=="":
  Host="127.0.0.1"
if Port=="":
  Port="32400"
if Section=="":
  Section = "1"
URL = ("http://" + Host + ":" + Port + "/library/sections/" + Section + "/recentlyViewed")
OnDeckURL = ("http://" + Host + ":" + Port + "/library/sections/" + Section + "/onDeck")
print("")
print("                           Detected Settings")
print("")
print("Host: " + Host)
print("Port: " + Port)
print("Section: " + Section)
print("URL: " + URL)
print("OnDeck URL: " + OnDeckURL)

####################################################################################
##  Checking Shows
####################################################################################
NoDelete = " | "
ShowCount = len(Shows)
print("Show Count: " + str(ShowCount))

for Show in Shows:
  Show = re.sub('[^A-Za-z0-9 ]+', '', Show).strip()
  if Show=="":
    NoDelete += "(None Listed) | "
    ShowCount -= 1
  else:
    NoDelete += Show + " | "

print("Number of Shows Detected For Keeping: " + str(ShowCount))
print ("Shows to Keep:" + NoDelete)

###################################################################################
##  Checking Delete
####################################################################################
if Delete=="1":
  print("Delete: ***Enabled***")
else:
  print("Delete: Disabled - Flagging Only")

if OnDeck=="1":
  print("Delete OnDeck: No")
else:
  print("Delete OnDeck: Yes")

####################################################################################
##  Checking OS
####################################################################################
AD = ""
if PC=="":
  AD = "(Auto Detected)"
  if platform.system()=="Windows":
    PC = "W"
  elif platform.system()=="Linux":
    PC = "L"
  elif platform.system()=="Darwin":
    PC = "L"

####################################################################################
##  Setting OS Based Variables
####################################################################################
if PC=="L":
  print("Operating System: Linux " + AD)
  from urllib.request import urlopen
  doc = xml.dom.minidom.parse(urlopen(URL))
  deck = xml.dom.minidom.parse(urlopen(OnDeckURL))
elif PC=="W":
  print("Operating System: Windows " + AD)
  import urllib.request
  doc = xml.dom.minidom.parse(urllib.request.urlopen(URL))
  deck = xml.dom.minidom.parse(urllib.request.urlopen(OnDeckURL))
else:
  print("Operating System: ** Not Configured **  (" + platform.system() + ") is not recognized.")
  exit()
print("")
print("")
print("")

FileCount = 0
DeleteCount = 0
FlaggedCount = 0
OnDeckCount = 0
ShowsCount = 0

####################################################################################
##  Check On Deck
####################################################################################
def CheckOnDeck( CheckDeckFile ):
  InTheDeck = 0
  for DeckVideoNode in deck.getElementsByTagName("Video"):
    DeckMediaNode = DeckVideoNode.getElementsByTagName("Media")
    for DeckMedia in DeckMediaNode:
      DeckPartNode = DeckMedia.getElementsByTagName("Part")
      for DeckPart in DeckPartNode:
        Deckfile = DeckPart.getAttribute("file")
        if CheckDeckFile==Deckfile:
          InTheDeck += 1
        else:
          InTheDeck += 0
  return InTheDeck
 
####################################################################################
##  Check Shows And Delete If Configured
####################################################################################
def CheckShows( CheckFile ):
  global FileCount
  global DeleteCount
  global FlaggedCount
  global OnDeckCount
  global ShowsCount
  FileCount += 1
  CantDelete = 0
  ShowFound = ""
 
##  -- CHECK SHOWS --  
  for Show in Shows:
    Show = re.sub('[^A-Za-z0-9 ]+', '', Show).strip()
    if Show=="":
      CantDelete = 0
    else:
      if (' ' in Show) == True:
        if all(str(Word) in CheckFile for Word in Show.split()):
          CantDelete += 1
          ShowFound = "[" + Show + "]"
          ShowsCount += 1
        else:
          CantDelete += 0
      else:
        if Show in CheckFile:
          CantDelete += 1
          ShowFound = "[" + Show + "]"
          ShowsCount += 1
        else:
          CantDelete += 0

## -- Check OnDeck --
  if OnDeck=="1":
    IsOnDeck = CheckOnDeck(CheckFile);
    if IsOnDeck==0:
      CantDelete += 0
    else:
      CantDelete += 1
      ShowFound = "[OnDeck]" + ShowFound
      OnDeckCount += 1

## -- DELETE SHOWS --
  if CantDelete == 0:
    if Delete=="1":
      print("**[DELETED] " + CheckFile)
      os.remove(file)
      DeleteCount += 1
    else:
      print("**[FLAGGED] " + CheckFile)
      FlaggedCount += 1
  else:
    print("[KEEPING]" + ShowFound + " " + CheckFile)

####################################################################################
##  Get Files for Watched Shows
####################################################################################
for VideoNode in doc.getElementsByTagName("Video"):
  view = VideoNode.getAttribute("viewCount")
  if view == '':
    view = 0
  view = int(view)
  MediaNode = VideoNode.getElementsByTagName("Media")
  for Media in MediaNode:
    PartNode = Media.getElementsByTagName("Part")
    for Part in PartNode:
      file = Part.getAttribute("file")
      if view > 0:
          if os.path.isfile(file):
            CheckShows(file);
          else:
            print("##[NOT FOUND] " + file)

####################################################################################
##  Check Shows And Delete If Configured
####################################################################################    
print("")
print("")
print("")
print("Summary -- Script Completed Successfully")
print("")
print("")
print("  Total File Count  " + str(FileCount))
print("  Kept Show Files   " + str(ShowsCount))
print("  On Deck Files     " + str(OnDeckCount))
print("  Deleted Files     " + str(DeleteCount))
print("  Flagged Files     " + str(FlaggedCount))
print("")
print("")
print("")